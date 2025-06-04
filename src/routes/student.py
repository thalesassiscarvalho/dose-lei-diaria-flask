# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify # Adicionado jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_ # Import or_ for searching
from src.models.user import db, Achievement, Announcement # Import Achievement and Announcement
from src.models.law import Law, Subject # Import Subject
from src.models.progress import UserProgress
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
        Achievement.id.notin_([a.id for a in user.achievements]) # Only check achievements the user doesn't have
    ).all()
    logging.debug(f"[ACHIEVEMENT CHECK] Potential point achievements: {[a.name for a in potential_point_achievements]}")
    
    for achievement in potential_point_achievements:
        if user.points >= achievement.points_threshold:
            logging.debug(f"[ACHIEVEMENT CHECK] Awarding point achievement \t{achievement.name}\t to user {user.id}")
            user.achievements.append(achievement)
            unlocked_achievements_names.append(achievement.name)
            
    # --- Check Achievements based on Laws Completed ---
    # UPDATED: Count based on status == 'concluido'
    completed_laws_count = UserProgress.query.filter(
        UserProgress.user_id == user.id,
        UserProgress.status == 'concluido' 
    ).count()
    logging.debug(f"[ACHIEVEMENT CHECK] User {user.id} completed laws count (status 'concluido'): {completed_laws_count}")
    
    potential_law_achievements = Achievement.query.filter(
        Achievement.laws_completed_threshold != None,
        Achievement.id.notin_([a.id for a in user.achievements]) # Only check achievements the user doesn't have
    ).all()
    logging.debug(f"[ACHIEVEMENT CHECK] Potential law achievements: {[a.name for a in potential_law_achievements]}")

    for achievement in potential_law_achievements:
        if completed_laws_count >= achievement.laws_completed_threshold:
            logging.debug(f"[ACHIEVEMENT CHECK] Awarding law achievement \t{achievement.name}\t to user {user.id}")
            user.achievements.append(achievement)
            unlocked_achievements_names.append(achievement.name)
        
    # Commit changes if any achievements were awarded (done outside this function after calling it)
    # Return the names of newly unlocked achievements to display a message
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
    # --- NOVO: Obter filtro de favoritos --- 
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
    completed_law_ids = {law_id for law_id, status in progress_map.items() if status == 'concluido'}
    in_progress_law_ids = {law_id for law_id, status in progress_map.items() if status == 'em_andamento'}

    # --- NOVO: Obter IDs das leis favoritas --- 
    # Usando o relacionamento definido no modelo User (assumindo que foi adicionado como 'favorite_laws')
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

            if selected_status == 'completed' and is_completed:
                laws_after_status_filter.append(law)
            elif selected_status == 'in_progress' and is_in_progress:
                laws_after_status_filter.append(law)
            elif selected_status == 'not_read' and is_not_read:
                laws_after_status_filter.append(law)

    # --- NOVO: Aplicar filtro de favoritos --- 
    laws_to_display = []
    if show_favorites:
        # Se o filtro de favoritos estiver ativo, filtre a lista que já passou pelo filtro de status
        laws_to_display = [law for law in laws_after_status_filter if law.id in favorite_law_ids]
        logging.debug(f"[DASHBOARD] Filtering for favorites. Laws count: {len(laws_to_display)}")
    else:
        # Se não, use a lista que passou pelo filtro de status
        laws_to_display = laws_after_status_filter
    # --- Fim do filtro de favoritos ---

    total_laws_count = Law.query.count()
    completed_count = len(completed_law_ids)
    progress_percentage = (completed_count / total_laws_count * 100) if total_laws_count > 0 else 0

    user_points = current_user.points
    user_achievements = current_user.achievements

    newly_unlocked = check_and_award_achievements(current_user)
    if newly_unlocked:
        try:
            db.session.commit()
            user_achievements = current_user.achievements
            flash(f"Novas conquistas desbloqueadas: {', '.join(newly_unlocked)}!", "success")
        except Exception as e:
            db.session.rollback()
            logging.error(f"[DASHBOARD] Error committing achievements for user {current_user.id}: {e}")
            flash("Erro ao atualizar conquistas.", "danger")
        
    active_announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).all()
    
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
                           announcements=active_announcements,
                           selected_status=selected_status,
                           # --- NOVO: Passar dados de favoritos para o template ---
                           favorite_law_ids=favorite_law_ids, 
                           show_favorites=show_favorites # Passar estado do checkbox
                           )

# --- NOVO: Rota para Adicionar/Remover Favorito ---
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
# --- FIM NOVO ---

@student_bp.route("/law/<int:law_id>")
@login_required
def view_law(law_id):
    law = Law.query.get_or_404(law_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    
    current_status = progress.status if progress else 'nao_iniciado'
    is_completed = current_status == 'concluido'
    
    last_read_article = progress.last_read_article if progress else None 
    return render_template("student/view_law.html", 
                           law=law, 
                           is_completed=is_completed, 
                           last_read_article=last_read_article,
                           current_status=current_status)

@student_bp.route("/law/mark_complete/<int:law_id>", methods=["POST"])
@login_required
def mark_complete(law_id):
    law = Law.query.get_or_404(law_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()

    points_awarded_this_time = 0
    was_already_completed = False

    if not progress:
        logging.debug(f"[MARK COMPLETE] No progress found for user {current_user.id}, law {law_id}. Creating new.")
        progress = UserProgress(user_id=current_user.id, law_id=law_id)
        db.session.add(progress)
    else:
        logging.debug(f"[MARK COMPLETE] Progress found for user {current_user.id}, law {law_id}. Current status: {progress.status}")
        if progress.status == 'concluido':
            was_already_completed = True

    if was_already_completed:
        flash(f"Você já marcou a lei \"{law.title}\" como concluída.", "info")
    else:
        points_to_award = 10 
        current_user.points += points_to_award
        points_awarded_this_time = points_to_award
        db.session.add(current_user)
        logging.debug(f"[MARK COMPLETE] Awarding {points_to_award} points to user {current_user.id}. New total: {current_user.points}")
        
        progress.status = 'concluido'
        progress.completed_at = datetime.datetime.utcnow()
        logging.debug(f"[MARK COMPLETE] Setting status to 'concluido' and completed_at for user {current_user.id}, law {law_id}.")

    unlocked_achievements = check_and_award_achievements(current_user)
    
    try:
        db.session.commit()
        logging.info(f"[MARK COMPLETE] Successfully committed completion for user {current_user.id}, law {law_id}.")
        
        flash_message = f"Lei \"{law.title}\" marcada como concluída!"
        if points_awarded_this_time > 0:
             flash_message += f" Você ganhou {points_awarded_this_time} pontos."
        if unlocked_achievements:
            flash_message += f" Conquistas desbloqueadas: {', '.join(unlocked_achievements)}!"
        if not was_already_completed: # Only flash if it wasn't already completed
            flash(flash_message, "success")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[MARK COMPLETE] Error committing completion for user {current_user.id}, law {law_id}: {e}")
        flash(f"Erro ao marcar como concluído: {e}", "danger")

    # Redirect back to the law view page after marking complete
    return redirect(url_for("student.view_law", law_id=law_id))

@student_bp.route("/law/review/<int:law_id>", methods=["POST"])
@login_required
def review_law(law_id):
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()

    if progress:
        law_title = progress.law.title
        logging.debug(f"[REVIEW LAW] User {current_user.id} reviewing law {law_id}. Current status: {progress.status}")
        
        progress.status = 'em_andamento' 
        progress.completed_at = None 
        logging.debug(f"[REVIEW LAW] Setting status to 'em_andamento' and completed_at to None for user {current_user.id}, law {law_id}.")
        
        try:
            db.session.commit()
            logging.info(f"[REVIEW LAW] Successfully committed review status for user {current_user.id}, law {law_id}.")
            flash(f"O status de conclusão da lei \"{law_title}\" foi resetado. A lei está agora 'Em andamento'.", "info")
        except Exception as e:
            db.session.rollback()
            logging.error(f"[REVIEW LAW] Error committing review status for user {current_user.id}, law {law_id}: {e}")
            flash(f"Erro ao resetar status: {e}", "danger")
    else:
        logging.warning(f"[REVIEW LAW] Progress record not found for user {current_user.id}, law {law_id}.")
        flash("Não foi possível encontrar o registro de progresso para esta lei.", "warning")

    # Get current filters to maintain state on redirect
    search_query = request.args.get("search")
    subject_id = request.args.get("subject_id")
    status_filter = request.args.get("status_filter")
    # --- NOVO: Obter filtro de favoritos para manter no redirect ---
    show_favorites_val = request.args.get("show_favorites") # Get the value ('on' or None)

    redirect_url = url_for("student.dashboard", 
                           search=search_query, 
                           subject_id=subject_id, 
                           status_filter=status_filter,
                           # --- NOVO: Passar filtro de favoritos no redirect ---
                           show_favorites=show_favorites_val # Pass the value directly
                           )
    return redirect(redirect_url)

@student_bp.route("/law/save_last_read/<int:law_id>", methods=["POST"])
@login_required
def save_last_read(law_id):
    """Saves the last read article number for a given law and user."""
    last_article = request.form.get("last_article")
    logging.debug(f"[SAVE LAST READ] User {current_user.id}, Law {law_id}, Article: '{last_article}'")
    
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    is_new_progress = not progress

    if is_new_progress:
        logging.debug(f"[SAVE LAST READ] No progress found. Creating new record.")
        initial_status = 'em_andamento' if last_article else 'nao_iniciado'
        progress = UserProgress(
            user_id=current_user.id,
            law_id=law_id,
            completed_at=None,
            status=initial_status,
            last_read_article=last_article if last_article else None
        )
        db.session.add(progress)
        logging.debug(f"[SAVE LAST READ] New progress created with status: {initial_status}, article: {progress.last_read_article}")
    else:
        logging.debug(f"[SAVE LAST READ] Progress found. Current status: {progress.status}")
        progress.last_read_article = last_article if last_article else None
        logging.debug(f"[SAVE LAST READ] Updated last_read_article to: {progress.last_read_article}")

        if progress.status == 'nao_iniciado':
            if last_article:
                progress.status = 'em_andamento'
                logging.debug(f"[SAVE LAST READ] Status changed from 'nao_iniciado' to 'em_andamento'.")
        elif progress.status == 'em_andamento':
            # Keep 'em_andamento' even if article is cleared
            pass 
        elif progress.status == 'concluido':
             logging.debug(f"[SAVE LAST READ] Status is 'concluido', not changing status.")

    if progress.status != 'concluido':
        progress.completed_at = None 

    try:
        db.session.commit()
        logging.info(f"[SAVE LAST READ] Successfully committed progress for user {current_user.id}, law {law_id}. New status: {progress.status}")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[SAVE LAST READ] Error committing progress for user {current_user.id}, law {law_id}: {e}")
        # Return error in JSON for AJAX call
        return jsonify(success=False, error=str(e)), 500
        
    # Return success in JSON for AJAX call
    return jsonify(success=True, message="Posição salva."), 200

