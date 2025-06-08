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
            flash(f"Novas conquistas desbloqueadas: {', '.join(newly_unlocked)}!", "success")
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

    # --- CORREÇÃO: Forçar expiração da sessão antes de buscar a última lei --- 
    logging.debug(f"[DASHBOARD DEBUG] Expiring session cache before querying last accessed progress for user {current_user.id}")
    db.session.expire_all() # Força a busca dos dados mais recentes do DB
    # --- FIM CORREÇÃO ---

    # --- CORREÇÃO FINAL: Buscar a última lei acessada, IGNORANDO registros com last_accessed_at NULO --- 
    logging.debug(f"[DASHBOARD DEBUG] Querying last accessed progress for user {current_user.id} (excluding null last_accessed_at)")
    last_progress = UserProgress.query.filter(
        UserProgress.user_id == current_user.id,
        UserProgress.last_accessed_at.isnot(None) # <<<<<<<<<<<<<<<<<<< CORREÇÃO APLICADA AQUI
    ).order_by(UserProgress.last_accessed_at.desc()).first()
    # --- FIM CORREÇÃO FINAL ---
    
    if last_progress:
        logging.debug(f"[DASHBOARD DEBUG] Found last progress (not null): ID={last_progress.id}, LawID={last_progress.law_id}, LastAccessed={last_progress.last_accessed_at}")
    else:
        logging.debug(f"[DASHBOARD DEBUG] No progress with non-null last_accessed_at found for user {current_user.id}")
        
    last_accessed_law = last_progress.law if last_progress else None
    logging.debug(f"[DASHBOARD] Final last accessed law for user {current_user.id}: {last_accessed_law.title if last_accessed_law else 'None'}")

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
                           fixed_announcements=fixed_announcements, # Pass fixed announcements
                           non_fixed_announcements=non_fixed_unseen_announcements, # Pass non-fixed unseen announcements
                           selected_status=selected_status,
                           favorite_law_ids=favorite_law_ids, 
                           show_favorites=show_favorites,
                           last_accessed_law=last_accessed_law 
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
    
    now = datetime.datetime.utcnow()
    if progress:
        # --- LOG ADICIONADO --- 
        logging.debug(f"[VIEW LAW DEBUG] Found existing progress for Law {law_id}. Current LastAccessed: {progress.last_accessed_at}. Setting to: {now}")
        progress.last_accessed_at = now # Atualiza registro existente
    else:
        # Cria um novo registro de progresso se não existir, apenas por visualizar
        progress = UserProgress(
            user_id=current_user.id,
            law_id=law_id,
            status='nao_iniciado', # Define como não iniciado ao visualizar pela 1ª vez
            last_accessed_at=now
        )
        db.session.add(progress)
        # --- LOG ADICIONADO --- 
        logging.debug(f"[VIEW LAW DEBUG] Creating new progress for Law {law_id}. Setting LastAccessed to: {now}")

    try:
        db.session.commit() # Salva a atualização/criação do last_accessed_at
        # --- LOG ADICIONADO --- 
        logging.debug(f"[VIEW LAW DEBUG] Committed progress update/creation for Law {law_id}. Progress ID: {progress.id}, New LastAccessed: {progress.last_accessed_at}")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[VIEW LAW] Error updating/creating progress on view for user {current_user.id}, law {law_id}: {e}")
        # Não é crucial exibir erro para o usuário aqui, apenas logar

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
    now = datetime.datetime.utcnow() # Definir 'now' aqui

    if not progress:
        logging.debug(f"[MARK COMPLETE] No progress found for user {current_user.id}, law {law_id}. Creating new.")
        progress = UserProgress(user_id=current_user.id, law_id=law_id, last_accessed_at=now) 
        db.session.add(progress)
    else:
        logging.debug(f"[MARK COMPLETE] Progress found for user {current_user.id}, law {law_id}. Current status: {progress.status}")
        if progress.status == 'concluido':
            was_already_completed = True
        progress.last_accessed_at = now 
        # --- LOG ADICIONADO --- 
        logging.debug(f"[MARK COMPLETE DEBUG] Updating existing progress LastAccessed for Law {law_id} to: {now}")

    if was_already_completed:
        flash(f"Você já marcou a lei \"{law.title}\" como concluída.", "info")
    else:
        points_to_award = 10 
        current_user.points += points_to_award
        points_awarded_this_time = points_to_award
        db.session.add(current_user)
        logging.debug(f"[MARK COMPLETE] Awarding {points_to_award} points to user {current_user.id}. New total: {current_user.points}")
        
        progress.status = 'concluido'
        progress.completed_at = now # Usar 'now' aqui também
        logging.debug(f"[MARK COMPLETE] Setting status to 'concluido' and completed_at for user {current_user.id}, law {law_id}.")

    unlocked_achievements = check_and_award_achievements(current_user)
    
    try:
        db.session.commit()
        # --- LOG ADICIONADO --- 
        logging.debug(f"[MARK COMPLETE DEBUG] Committed progress update for Law {law_id}. Progress ID: {progress.id}, New LastAccessed: {progress.last_accessed_at}")
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

    return redirect(url_for("student.view_law", law_id=law_id))

# =====================================================================
# ROTA ADICIONADA PARA CORRIGIR O PROBLEMA
# =====================================================================
@student_bp.route("/law/review/<int:law_id>", methods=["POST"])
@login_required
def review_law(law_id):
    """
    Handles the "Marcar como não concluído" action.
    Sets a law's progress status back to 'em_andamento'.
    """
    # Find the progress record for the current user and the specific law.
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()

    if not progress:
        # This case is unlikely if the button is visible, but it's a good safeguard.
        return jsonify(success=False, error="Progresso não encontrado."), 404

    # Change the status back to 'in_progress'.
    # We do not deduct points here. The user can re-complete the law later.
    progress.status = 'em_andamento'
    
    # It's good practice to also clear the completion date.
    progress.completed_at = None

    try:
        # Commit the change to the database. This is the crucial step that was missing.
        db.session.commit()
        logging.info(f"[REVIEW LAW] User {current_user.id} set law {law_id} back to 'em_andamento'.")
        return jsonify(success=True, new_status='em_andamento')
    except Exception as e:
        db.session.rollback()
        logging.error(f"[REVIEW LAW] Error setting law {law_id} to 'em_andamento' for user {current_user.id}: {e}")
        return jsonify(success=False, error=str(e)), 500
# =====================================================================
# FIM DA ROTA ADICIONADA
# =====================================================================


# --- NOVA ROTA: Salvar onde parou via AJAX ---
@student_bp.route("/save_last_read/<int:law_id>", methods=["POST"])
@login_required
def save_last_read(law_id):
    """Salva o ponto onde o usuário parou de ler via AJAX."""
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
            status='em_andamento',  # Marcar como em andamento ao salvar onde parou
            last_accessed_at=now,
            last_read_article=last_read_article
        )
        db.session.add(progress)
        logging.debug(f"[SAVE LAST READ] Creating new progress for user {current_user.id}, law {law_id}, article: {last_read_article}")
    else:
        progress.last_read_article = last_read_article
        progress.last_accessed_at = now
        
        # Se não estiver concluído, marcar como em andamento
        if progress.status != 'concluido':
            progress.status = 'em_andamento'
            
        logging.debug(f"[SAVE LAST READ] Updating progress for user {current_user.id}, law {law_id}, article: {last_read_article}")
    
    try:
        db.session.commit()
        logging.info(f"[SAVE LAST READ] Successfully saved last read article for user {current_user.id}, law {law_id}: {last_read_article}")
        return jsonify(success=True, message="Ponto de leitura salvo com sucesso!")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[SAVE LAST READ] Error saving last read article for user {current_user.id}, law {law_id}: {e}")
        return jsonify(success=False, error=str(e)), 500
# --- FIM NOVA ROTA ---

@student_bp.route("/announcement/<int:announcement_id>/mark_seen", methods=["POST"])
@login_required
def mark_announcement_seen(announcement_id):
    """Mark an announcement as seen by the current user."""
    announcement = Announcement.query.get_or_404(announcement_id)
    
    # Check if already marked as seen
    existing = UserSeenAnnouncement.query.filter_by(
        user_id=current_user.id, 
        announcement_id=announcement_id
    ).first()
    
    if not existing:
        seen_record = UserSeenAnnouncement(
            user_id=current_user.id,
            announcement_id=announcement_id
        )
        db.session.add(seen_record)
        
        try:
            db.session.commit()
            logging.info(f"[ANNOUNCEMENT] User {current_user.id} marked announcement {announcement_id} as seen.")
            return jsonify(success=True)
        except Exception as e:
            db.session.rollback()
            logging.error(f"[ANNOUNCEMENT] Error marking announcement {announcement_id} as seen for user {current_user.id}: {e}")
            return jsonify(success=False, error=str(e)), 500
    else:
        # Already marked as seen, just return success
        return jsonify(success=True)

# --- Rotas para as ANOTAÇÕES GERAIS do usuário (antigo "notes") ---
@student_bp.route("/law/<int:law_id>/notes", methods=["GET"])
@login_required
def get_user_notes(law_id):
    """Retorna as anotações gerais do usuário atual para uma lei específica."""
    notes = UserNotes.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    
    if notes:
        return jsonify(success=True, content=notes.content)
    else:
        return jsonify(success=True, content="")

@student_bp.route("/law/<int:law_id>/notes", methods=["POST"])
@login_required
def save_user_notes(law_id):
    """Salva ou atualiza as anotações gerais do usuário atual para uma lei específica."""
    content = request.json.get("content", "")
    
    notes = UserNotes.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    
    if notes:
        notes.content = content
        notes.updated_at = datetime.datetime.utcnow()
    else:
        notes = UserNotes(
            user_id=current_user.id,
            law_id=law_id,
            content=content
        )
        db.session.add(notes)
    
    try:
        db.session.commit()
        logging.info(f"[SAVE GENERAL NOTES] Successfully saved general notes for user {current_user.id}, law {law_id}")
        return jsonify(success=True, message="Anotações gerais salvas com sucesso!")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[SAVE GENERAL NOTES] Error saving general notes for user {current_user.id}, law {law_id}: {e}")
        return jsonify(success=False, error="Erro ao salvar anotações gerais."), 500

# =====================================================================
# <<< INÍCIO: NOVAS ROTAS DA API DE ANOTAÇÕES POR PARÁGRAFO (antigo "comments") >>>
# =====================================================================

@student_bp.route("/law/<int:law_id>/comments", methods=["GET"])
@login_required
def get_comments(law_id):
    """Carrega todas as anotações por parágrafo do usuário atual para uma lei específica."""
    comments = UserComment.query.filter_by(user_id=current_user.id, law_id=law_id).order_by(UserComment.created_at.asc()).all()
    
    comments_data = [{
        "id": comment.id,
        "content": comment.content,
        "anchor_paragraph_id": comment.anchor_paragraph_id,
        "created_at": comment.created_at.strftime("%d/%m/%Y às %H:%M")
    } for comment in comments]
    
    return jsonify(success=True, comments=comments_data)

@student_bp.route("/law/<int:law_id>/comments", methods=["POST"])
@login_required
def add_comment(law_id):
    """Adiciona uma nova anotação a um parágrafo de uma lei."""
    data = request.json
    content = data.get("content")
    anchor_id = data.get("anchor_paragraph_id")

    if not content or not anchor_id:
        return jsonify(success=False, error="Dados incompletos."), 400

    try:
        new_comment = UserComment(
            content=content,
            anchor_paragraph_id=anchor_id,
            user_id=current_user.id,
            law_id=law_id
        )
        db.session.add(new_comment)
        db.session.commit()
        
        comment_data = {
            "id": new_comment.id,
            "content": new_comment.content,
            "anchor_paragraph_id": new_comment.anchor_paragraph_id,
            "created_at": new_comment.created_at.strftime("%d/%m/%Y às %H:%M")
        }
        
        return jsonify(success=True, message="Anotação salva!", comment=comment_data), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"[ADD ANNOTATION] Erro ao salvar anotação para user {current_user.id}: {e}")
        return jsonify(success=False, error="Erro interno ao salvar a anotação."), 500

@student_bp.route("/comments/<int:comment_id>", methods=["PUT"])
@login_required
def update_comment(comment_id):
    """Atualiza uma anotação existente."""
    comment = UserComment.query.get_or_404(comment_id)

    if comment.user_id != current_user.id:
        return jsonify(success=False, error="Ação não autorizada."), 403

    data = request.json
    new_content = data.get("content")

    if not new_content:
        return jsonify(success=False, error="O conteúdo não pode ser vazio."), 400
    
    try:
        comment.content = new_content
        if hasattr(comment, 'updated_at'):
            comment.updated_at = datetime.datetime.utcnow()
            
        db.session.commit()
        
        updated_comment_data = {
            "id": comment.id,
            "content": comment.content,
        }
        
        return jsonify(success=True, message="Anotação atualizada!", comment=updated_comment_data)
    except Exception as e:
        db.session.rollback()
        logging.error(f"[UPDATE ANNOTATION] Erro ao atualizar anotação {comment_id}: {e}")
        return jsonify(success=False, error="Erro interno ao atualizar a anotação."), 500

@student_bp.route("/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_comment(comment_id):
    """Exclui uma anotação."""
    comment = UserComment.query.get_or_404(comment_id)

    if comment.user_id != current_user.id:
        return jsonify(success=False, error="Ação não autorizada."), 403

    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify(success=True, message="Anotação excluída.")
    except Exception as e:
        db.session.rollback()
        logging.error(f"[DELETE ANNOTATION] Erro ao excluir anotação {comment_id}: {e}")
        return jsonify(success=False, error="Erro interno ao excluir a anotação."), 500
