# ARQUIVO ATUALIZADO: src/routes/student.py

# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify # Adicionado jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_ # Import or_ for searching
# Modificado: Adicionado User ao import
from src.models.user import db, Achievement, Announcement, User, UserSeenAnnouncement # Added UserSeenAnnouncement 
from src.models.law import Law, Subject # Import Subject
from src.models.progress import UserProgress
from src.models.notes import UserNotes # Importar o novo modelo de anotações
from src.models.comment import UserComment # <<< NOVO IMPORT
import datetime
import logging # Import logging

student_bp = Blueprint("student", __name__, url_prefix="/student")

# --- Helper Function for Gamification ---
def check_and_award_achievements(user):
    """Checks if the user qualifies for any new achievements and awards them."""
    unlocked_achievements_names = []
    logging.debug(f"[ACHIEVEMENT CHECK] User: {user.id}")

    # --- Check Achievements based on Points ---
    potential_point_achievements = Achievement.query.filter(
        Achievement.points_threshold != None,
        Achievement.id.notin_([a.id for a in user.achievements]) # Only check achievements the user doesn\'t have
    ).all()
    logging.debug(f"[ACHIEVEMENT CHECK] Potential point achievements: {[a.name for a in potential_point_achievements]}")

    for achievement in potential_point_achievements:
        if user.points >= achievement.points_threshold:
            logging.debug(f"[ACHIEVEMENT CHECK] Awarding point achievement \t{achievement.name}\t to user {user.id}")
            user.achievements.append(achievement)
            unlocked_achievements_names.append(achievement.name)

    # --- Check Achievements based on Laws Completed ---
    # UPDATED: Count based on status == \'concluido\'
    completed_laws_count = UserProgress.query.filter(
        UserProgress.user_id == user.id,
        UserProgress.status == 'concluido'
    ).count()
    logging.debug(f"[ACHIEVEMENT CHECK] User {user.id} completed laws count (status \'concluido\'): {completed_laws_count}")

    potential_law_achievements = Achievement.query.filter(
        Achievement.laws_completed_threshold != None,
        Achievement.id.notin_([a.id for a in user.achievements]) # Only check achievements the user doesn\'t have
    ).all()
    logging.debug(f"[ACHIEVEMENT CHECK] Potential law achievements: {[a.name for a in potential_law_achievements]}")

    for achievement in potential_law_achievements:
        if completed_laws_count >= achievement.laws_completed_threshold:
            logging.debug(f"[ACHIEVEMENT CHECK] Awarding law achievement \t{achievement.name}\t to user {user.id}")
            user.achievements.append(achievement)
            unlocked_achievements_names.append(achievement.name)

    logging.debug(f"[ACHIEVEMENT CHECK] Newly unlocked for user {user.id}: {unlocked_achievements_names}")
    return unlocked_achievements_names

# --- Routes ---

@student_bp.route("/dashboard")
@login_required
def dashboard():
    search_query = request.args.get("search", "")
    selected_subject_id_str = request.args.get("subject_id", "") 
    selected_subject_id = int(selected_subject_id_str) if selected_subject_id_str.isdigit() else None
    selected_status = request.args.get("status_filter", "")
    show_favorites = request.args.get("show_favorites") == 'on' # Checkbox envia 'on' se marcado

    # Fetch all subjects for the filter dropdown
    subjects = Subject.query.order_by(Subject.name).all()

    # Base query for laws
    laws_query = Law.query.join(Subject, Law.subject_id == Subject.id, isouter=True).order_by(Subject.name, Law.title)

    # Apply subject filter
    if selected_subject_id:
        laws_query = laws_query.filter(Law.subject_id == selected_subject_id)

    # Apply search filter
    if search_query:
        search_term = f"%{search_query}%"
        laws_query = laws_query.filter(
            or_(
                Law.title.ilike(search_term),
                Law.description.ilike(search_term)
            )
        )

    laws_after_initial_filters = laws_query.all()

    # Fetch progress records
    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    progress_map = {p.law_id: p.status for p in user_progress_records}
    completed_law_ids = {law_id for law_id, status in progress_map.items() if status == \'concluido\'}
    in_progress_law_ids = {law_id for law_id, status in progress_map.items() if status == \'em_andamento\'}

    favorite_law_ids = {law.id for law in current_user.favorite_laws}
    logging.debug(f"[DASHBOARD] User {current_user.id} favorite law IDs: {favorite_law_ids}")

    # Apply status filter
    laws_after_status_filter = []
    if not selected_status:
        laws_after_status_filter = laws_after_initial_filters
    else:
        for law in laws_after_initial_filters:
            is_completed = law.id in completed_law_ids
            is_in_progress = law.id in in_progress_law_ids
            is_not_read = not is_completed and not is_in_progress

            if selected_status == \'completed\' and is_completed:
                laws_after_status_filter.append(law)
            elif selected_status == \'in_progress\' and is_in_progress:
                laws_after_status_filter.append(law)
            elif selected_status == \'not_read\' and is_not_read:
                laws_after_status_filter.append(law)

    # Apply favorite filter
    laws_to_display = []
    if show_favorites:
        laws_to_display = [law for law in laws_after_status_filter if law.id in favorite_law_ids]
        logging.debug(f"[DASHBOARD] Filtering for favorites. Laws count: {len(laws_to_display)}")
    else:
        laws_to_display = laws_after_status_filter

    total_laws_count = Law.query.count()
    completed_count = len(completed_law_ids)
    progress_percentage = (completed_count / total_laws_count * 100) if total_laws_count > 0 else 0

    user_points = current_user.points
    user_achievements = current_user.achievements

    newly_unlocked = check_and_award_achievements(current_user)
    if newly_unlocked:
        try:
            db.session.commit()
            user_achievements = current_user.achievements # Refresh achievements after commit
            flash(f"Novas conquistas desbloqueadas: {\', \'.join(newly_unlocked)}!", "success")
        except Exception as e:
            db.session.rollback()
            logging.error(f"[DASHBOARD] Error committing achievements for user {current_user.id}: {e}")
            flash("Erro ao atualizar conquistas.", "danger")

    # Fetch announcements: Fixed and Non-Fixed (unseen by user)
    fixed_announcements = Announcement.query.filter_by(is_active=True, is_fixed=True).order_by(Announcement.created_at.desc()).all()

    seen_announcement_ids = db.session.query(UserSeenAnnouncement.announcement_id).filter_by(user_id=current_user.id).scalar_subquery()

    non_fixed_unseen_announcements = Announcement.query.filter(
        Announcement.is_active == True,
        Announcement.is_fixed == False,
        Announcement.id.notin_(seen_announcement_ids)
    ).order_by(Announcement.created_at.desc()).all()

    db.session.expire_all()

    last_progress = UserProgress.query.filter(
        UserProgress.user_id == current_user.id,
        UserProgress.last_accessed_at.isnot(None)
    ).order_by(UserProgress.last_accessed_at.desc()).first()

    last_accessed_law = last_progress.law if last_progress else None

    return render_template("student/dashboard.html", 
                           laws=laws_to_display,
                           subjects=subjects, 
                           selected_subject_id=selected_subject_id,
                           completed_law_ids=completed_law_ids,
                           in_progress_law_ids=in_progress_law_ids, 
                           progress_percentage=progress_percentage,
                           completed_count=completed_count,
                           total_laws=total_laws_count, 
                           search_query=search_query,
                           user_points=user_points, 
                           user_achievements=user_achievements, 
                           fixed_announcements=fixed_announcements, 
                           non_fixed_announcements=non_fixed_unseen_announcements,
                           selected_status=selected_status,
                           favorite_law_ids=favorite_law_ids, 
                           show_favorites=show_favorites,
                           last_accessed_law=last_accessed_law 
                           )

@student_bp.route("/law/toggle_favorite/<int:law_id>", methods=["POST"])
@login_required
def toggle_favorite(law_id):
    law = Law.query.get_or_404(law_id)
    is_currently_favorite = law in current_user.favorite_laws

    try:
        if is_currently_favorite:
            current_user.favorite_laws.remove(law)
            db.session.commit()
            logging.info(f"[FAVORITE] User {current_user.id} removed law {law_id} from favorites.")
            return jsonify(success=True, favorited=False)
        else:
            current_user.favorite_laws.append(law)
            db.session.commit()
            logging.info(f"[FAVORITE] User {current_user.id} added law {law_id} to favorites.")
            return jsonify(success=True, favorited=True)
    except Exception as e:
        db.session.rollback()
        logging.error(f"[FAVORITE] Error toggling favorite for user {current_user.id}, law {law_id}: {e}")
        return jsonify(success=False, error=str(e)), 500

@student_bp.route("/law/<int:law_id>")
@login_required
def view_law(law_id):
    law = Law.query.get_or_404(law_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()

    now = datetime.datetime.utcnow()
    if progress:
        logging.debug(f"[VIEW LAW DEBUG] Found existing progress for Law {law_id}. Current LastAccessed: {progress.last_accessed_at}. Setting to: {now}")
        progress.last_accessed_at = now
    else:
        progress = UserProgress(
            user_id=current_user.id,
            law_id=law_id,
            status=\'nao_iniciado\',
            last_accessed_at=now
        )
        db.session.add(progress)
        logging.debug(f"[VIEW LAW DEBUG] Creating new progress for Law {law_id}. Setting LastAccessed to: {now}")

    try:
        db.session.commit()
        logging.debug(f"[VIEW LAW DEBUG] Committed progress update/creation for Law {law_id}. Progress ID: {progress.id}, New LastAccessed: {progress.last_accessed_at}")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[VIEW LAW] Error updating/creating progress on view for user {current_user.id}, law {law_id}: {e}")

    current_status = progress.status if progress else \'nao_iniciado\'
    is_completed = current_status == \'concluido\'
    last_read_article = progress.last_read_article if progress else None

    # Fetch comments for the law
    comments = UserComment.query.filter_by(law_id=law_id).order_by(UserComment.created_at.asc()).all()

    return render_template("student/view_law.html", 
                           law=law, 
                           is_completed=is_completed, 
                           last_read_article=last_read_article,
                           current_status=current_status,
                           comments=comments) # Pass comments to the template

@student_bp.route("/law/mark_complete/<int:law_id>", methods=["POST"])
@login_required
def mark_complete(law_id):
    law = Law.query.get_or_404(law_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()

    points_awarded_this_time = 0
    was_already_completed = False
    now = datetime.datetime.utcnow()

    if not progress:
        logging.debug(f"[MARK COMPLETE] No progress found for user {current_user.id}, law {law_id}. Creating new.")
        progress = UserProgress(user_id=current_user.id, law_id=law_id, last_accessed_at=now) 
        db.session.add(progress)
    else:
        logging.debug(f"[MARK COMPLETE] Progress found for user {current_user.id}, law {law_id}. Current status: {progress.status}")
        if progress.status == \'concluido\':
            was_already_completed = True
        progress.last_accessed_at = now 
        logging.debug(f"[MARK COMPLETE DEBUG] Updating existing progress LastAccessed for Law {law_id} to: {now}")

    if was_already_completed:
        flash(f"Você já marcou a lei \"{law.title}\" como concluída.", "info")
    else:
        points_to_award = 10 
        current_user.points += points_to_award
        points_awarded_this_time = points_to_award
        db.session.add(current_user)
        logging.debug(f"[MARK COMPLETE] Awarding {points_to_award} points to user {current_user.id}. New total: {current_user.points}")

        progress.status = \'concluido\'
        progress.completed_at = now
        logging.debug(f"[MARK COMPLETE] Setting status to \'concluido\' and completed_at for user {current_user.id}, law {law_id}.")

    unlocked_achievements = check_and_award_achievements(current_user)

    try:
        db.session.commit()
        logging.debug(f"[MARK COMPLETE DEBUG] Committed progress update for Law {law_id}. Progress ID: {progress.id}, New LastAccessed: {progress.last_accessed_at}")
        logging.info(f"[MARK COMPLETE] Successfully committed completion for user {current_user.id}, law {law_id}.")

        flash_message = f"Lei \"{law.title}\" marcada como concluída!"
        if points_awarded_this_time > 0:
             flash_message += f" Você ganhou {points_awarded_this_time} pontos."
        if unlocked_achievements:
            flash_message += f" Conquistas desbloqueadas: {\', \'.join(unlocked_achievements)}!"
        if not was_already_completed:
            flash(flash_message, "success")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[MARK COMPLETE] Error committing completion for user {current_user.id}, law {law_id}: {e}")
        flash(f"Erro ao marcar como concluído: {e}", "danger")

    return redirect(url_for("student.view_law", law_id=law_id))

@student_bp.route("/law/review/<int:law_id>", methods=["POST"])
@login_required
def review_law(law_id):
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()

    if not progress:
        return jsonify(success=False, error="Progresso não encontrado."), 404

    progress.status = \'em_andamento\'
    progress.completed_at = None

    try:
        db.session.commit()
        logging.info(f"[REVIEW LAW] User {current_user.id} set law {law_id} back to \'em_andamento\'.")
        return jsonify(success=True, new_status=\'em_andamento\')
    except Exception as e:
        db.session.rollback()
        logging.error(f"[REVIEW LAW] Error setting law {law_id} to \'em_andamento\' for user {current_user.id}: {e}")
        return jsonify(success=False, error=str(e)), 500

@student_bp.route("/save_last_read/<int:law_id>", methods=["POST"])
@login_required
def save_last_read(law_id):
    law = Law.query.get_or_404(law_id)
    last_read_article = request.form.get("last_read_article", "").strip()

    if not last_read_article:
        return jsonify(success=False, error="Campo obrigatório não preenchido"), 400

    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    now = datetime.datetime.utcnow()

    if not progress:
        progress = UserProgress(
            user_id=current_user.id,
            law_id=law_id,
            status=\'em_andamento\',
            last_accessed_at=now,
            last_read_article=last_read_article
        )
        db.session.add(progress)
        logging.debug(f"[SAVE LAST READ] Creating new progress for user {current_user.id}, law {law_id}, article: {last_read_article}")
    else:
        progress.last_read_article = last_read_article
        progress.last_accessed_at = now

        if progress.status != \'concluido\':
            progress.status = \'em_andamento\'

        logging.debug(f"[SAVE LAST READ] Updating progress for user {current_user.id}, law {law_id}, article: {last_read_article}")

    try:
        db.session.commit()
        logging.info(f"[SAVE LAST READ] Successfully saved last read article for user {current_user.id}, law {law_id}.")
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        logging.error(f"[SAVE LAST READ] Error saving last read article for user {current_user.id}, law {law_id}: {e}")
        return jsonify(success=False, error=str(e)), 500

@student_bp.route("/add_comment/<int:law_id>", methods=["POST"])
@login_required
def add_comment(law_id):
    data = request.get_json()
    comment_text = data.get("comment_text")
    start_offset = data.get("start_offset")
    end_offset = data.get("end_offset")

    if not all([comment_text, start_offset is not None, end_offset is not None]):
        return jsonify(success=False, message="Dados incompletos para o comentário."), 400

    new_comment = UserComment(
        user_id=current_user.id,
        law_id=law_id,
        comment_text=comment_text,
        start_offset=start_offset,
        end_offset=end_offset
    )
    db.session.add(new_comment)
    try:
        db.session.commit()
        return jsonify(success=True, message="Comentário adicionado com sucesso!", comment={
            "id": new_comment.id,
            "user_name": current_user.username, # Ou current_user.name, dependendo do seu modelo User
            "comment_text": new_comment.comment_text,
            "start_offset": new_comment.start_offset,
            "end_offset": new_comment.end_offset,
            "created_at": new_comment.created_at.isoformat() # Para formatar a data para JS
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao adicionar comentário: {e}")
        return jsonify(success=False, message="Erro interno ao adicionar comentário."), 500

@student_bp.route("/get_comments/<int:law_id>", methods=["GET"])
@login_required
def get_comments(law_id):
    comments = UserComment.query.filter_by(law_id=law_id).order_by(UserComment.created_at.asc()).all()
    comments_data = []
    for comment in comments:
        comments_data.append({
            "id": comment.id,
            "user_name": comment.user.username, # Assumindo que UserComment tem um relacionamento com User
            "comment_text": comment.comment_text,
            "start_offset": comment.start_offset,
            "end_offset": comment.end_offset,
            "created_at": comment.created_at.isoformat()
        })
    return jsonify(comments_data)

@student_bp.route("/delete_comment/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_comment(comment_id):
    comment = UserComment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        return jsonify(success=False, message="Você não tem permissão para deletar este comentário."), 403
    
    db.session.delete(comment)
    try:
        db.session.commit()
        return jsonify(success=True, message="Comentário deletado com sucesso!")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao deletar comentário: {e}")
        return jsonify(success=False, message="Erro interno ao deletar comentário."), 500

