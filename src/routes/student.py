# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from src.models.user import db, Achievement, Announcement, User, UserSeenAnnouncement
from src.models.law import Law, Subject
from src.models.progress import UserProgress
from src.models.notes import UserNotes
from src.models.comment import UserComment
import datetime
import logging

student_bp = Blueprint("student", __name__, url_prefix="/student")

def check_and_award_achievements(user):
    """Verifica e concede conquistas ao usuário."""
    unlocked_achievements_names = []
    completed_laws_count = UserProgress.query.filter_by(user_id=user.id, status='concluido').count()
    all_achievements = Achievement.query.all()
    user_achievement_ids = {a.id for a in user.achievements}

    for achievement in all_achievements:
        if achievement.id not in user_achievement_ids:
            unlocked = False
            if achievement.points_threshold and user.points >= achievement.points_threshold:
                unlocked = True
            if achievement.laws_completed_threshold and completed_laws_count >= achievement.laws_completed_threshold:
                unlocked = True
            
            if unlocked:
                user.achievements.append(achievement)
                unlocked_achievements_names.append(achievement.name)
    
    return unlocked_achievements_names

@student_bp.route("/dashboard")
@login_required
def dashboard():
    search_query = request.args.get("search", "")
    selected_subject_id_str = request.args.get("subject_id", "")
    selected_subject_id = int(selected_subject_id_str) if selected_subject_id_str.isdigit() else None
    selected_status = request.args.get("status_filter", "")
    show_favorites = request.args.get("show_favorites") == 'on'
    
    subjects_for_filter = Subject.query.order_by(Subject.name).all()

    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    progress_map = {p.law_id: p.status for p in user_progress_records}
    completed_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'concluido'}
    in_progress_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'em_andamento'}
    favorite_topic_ids = {law.id for law in current_user.favorite_laws if law.parent_id is not None}

    # =====================================================================
    # <<< INÍCIO DA QUERY HIERÁRQUICA CORRIGIDA >>>
    # =====================================================================
    diplomas_query = Law.query.outerjoin(Subject).filter(Law.parent_id.is_(None)).options(
        joinedload(Law.children)
    )
    # =====================================================================
    # <<< FIM DA QUERY HIERÁRQUICA CORRIGIDA >>>
    # =====================================================================

    if selected_subject_id:
        diplomas_query = diplomas_query.filter(Law.subject_id == selected_subject_id)
    
    if search_query:
        search_term = f"%{search_query}%"
        diplomas_query = diplomas_query.filter(
            or_(
                Law.title.ilike(search_term),
                Law.children.any(Law.title.ilike(search_term))
            )
        )
    
    # A ordenação é feita após todos os filtros serem aplicados
    all_diplomas = diplomas_query.order_by(Subject.name, Law.title).all()
    
    processed_diplomas = []
    for diploma in all_diplomas:
        children_to_display = []
        # No modelo corrigido, diploma.children já é uma lista, não precisa de .all()
        for topic in diploma.children:
            is_completed = topic.id in completed_topic_ids
            is_in_progress = topic.id in in_progress_topic_ids
            is_not_read = not is_completed and not is_in_progress
            is_favorite = topic.id in favorite_topic_ids

            passes_status = (not selected_status or
                             (selected_status == 'completed' and is_completed) or
                             (selected_status == 'in_progress' and is_in_progress) or
                             (selected_status == 'not_read' and is_not_read))
            
            passes_favorite = not show_favorites or is_favorite

            if passes_status and passes_favorite:
                children_to_display.append(topic)
        
        is_any_filter_active = selected_status or show_favorites or search_query
        if children_to_display or not is_any_filter_active:
            # Usamos len() em vez de .count() porque agora é uma lista
            total_children = len(diploma.children)
            completed_children_count = sum(1 for child in diploma.children if child.id in completed_topic_ids)
            diploma.progress_percentage = (completed_children_count / total_children * 100) if total_children > 0 else 0
            diploma.filtered_children = children_to_display if is_any_filter_active else diploma.children
            
            if diploma.filtered_children or not is_any_filter_active:
                 processed_diplomas.append(diploma)

    subjects_with_diplomas = {}
    for diploma in processed_diplomas:
        subject_name = diploma.subject.name if diploma.subject else "Sem Matéria"
        if subject_name not in subjects_with_diplomas:
            subjects_with_diplomas[subject_name] = []
        subjects_with_diplomas[subject_name].append(diploma)

    total_topics_count = Law.query.filter(Law.parent_id.isnot(None)).count()
    completed_count = len(completed_topic_ids)
    global_progress_percentage = (completed_count / total_topics_count * 100) if total_topics_count > 0 else 0
    
    last_progress = UserProgress.query.join(Law).filter(
        UserProgress.user_id == current_user.id,
        UserProgress.last_accessed_at.isnot(None),
        Law.parent_id.isnot(None)
    ).order_by(UserProgress.last_accessed_at.desc()).first()
    last_accessed_law = last_progress.law if last_progress else None
    
    fixed_announcements = Announcement.query.filter_by(is_active=True, is_fixed=True).order_by(Announcement.created_at.desc()).all()
    seen_announcement_ids = db.session.query(UserSeenAnnouncement.announcement_id).filter_by(user_id=current_user.id).scalar_subquery()
    non_fixed_announcements = Announcement.query.filter(
        Announcement.is_active==True, Announcement.is_fixed==False, Announcement.id.notin_(seen_announcement_ids)
    ).order_by(Announcement.created_at.desc()).all()
    
    return render_template("student/dashboard.html",
                           subjects_with_diplomas=subjects_with_diplomas,
                           subjects=subjects_for_filter,
                           selected_subject_id=selected_subject_id,
                           completed_law_ids=completed_topic_ids,
                           in_progress_law_ids=in_progress_topic_ids,
                           favorite_law_ids=favorite_topic_ids,
                           progress_percentage=global_progress_percentage,
                           completed_count=completed_count,
                           total_laws=total_topics_count,
                           search_query=search_query,
                           selected_status=selected_status,
                           show_favorites=show_favorites,
                           user_points=current_user.points,
                           user_achievements=current_user.achievements,
                           fixed_announcements=fixed_announcements,
                           non_fixed_announcements=non_fixed_announcements,
                           last_accessed_law=last_accessed_law)


@student_bp.route("/law/<int:law_id>")
@login_required
def view_law(law_id):
    law = Law.query.get_or_404(law_id)
    if law.parent_id is None:
        flash("Selecione um tópico de estudo específico para visualizar.", "info")
        return redirect(url_for('student.dashboard'))
    
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    now = datetime.datetime.utcnow()
    
    if progress:
        progress.last_accessed_at = now
    else:
        progress = UserProgress(user_id=current_user.id, law_id=law_id, status='em_andamento', last_accessed_at=now)
        db.session.add(progress)
        
    db.session.commit()
    is_favorited = law in current_user.favorite_laws

    return render_template("student/view_law.html", 
                           law=law, 
                           is_completed=(progress.status == 'concluido'), 
                           last_read_article=progress.last_read_article,
                           current_status=progress.status,
                           is_favorited=is_favorited)


@student_bp.route("/law/toggle_favorite/<int:law_id>", methods=["POST"])
@login_required
def toggle_favorite(law_id):
    law = Law.query.get_or_404(law_id)
    try:
        if law in current_user.favorite_laws:
            current_user.favorite_laws.remove(law)
            db.session.commit()
            return jsonify(success=True, favorited=False)
        else:
            current_user.favorite_laws.append(law)
            db.session.commit()
            return jsonify(success=True, favorited=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@student_bp.route("/law/mark_complete/<int:law_id>", methods=["POST"])
@login_required
def mark_complete(law_id):
    law = Law.query.get_or_404(law_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    was_already_completed = progress and progress.status == 'concluido'

    if not was_already_completed:
        points_to_award = 10
        current_user.points += points_to_award
        
        if not progress:
            progress = UserProgress(user_id=current_user.id, law_id=law_id)
            db.session.add(progress)
        
        progress.status = 'concluido'
        progress.completed_at = datetime.datetime.utcnow()
        
        unlocked = check_and_award_achievements(current_user)
        try:
            db.session.commit()
            flash_message = f"Lei \"{law.title}\" marcada como concluída! Você ganhou {points_to_award} pontos."
            if unlocked:
                flash_message += f" Conquistas desbloqueadas: {', '.join(unlocked)}!"
            flash(flash_message, "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar progresso: {e}", "danger")
    else:
        flash(f"Você já marcou \"{law.title}\" como concluída.", "info")

    return redirect(url_for("student.view_law", law_id=law_id))


@student_bp.route("/law/review/<int:law_id>", methods=["POST"])
@login_required
def review_law(law_id):
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    if not progress:
        return jsonify(success=False, error="Progresso não encontrado."), 404
    
    progress.status = 'em_andamento'
    progress.completed_at = None
    try:
        db.session.commit()
        return jsonify(success=True, new_status='em_andamento')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@student_bp.route("/save_last_read/<int:law_id>", methods=["POST"])
@login_required
def save_last_read(law_id):
    last_read_article = request.form.get("last_read_article", "").strip()
    if not last_read_article:
        return jsonify(success=False, error="Campo obrigatório"), 400
    
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    
    if not progress:
        progress = UserProgress(user_id=current_user.id, law_id=law_id, status='em_andamento')
        db.session.add(progress)
    
    progress.last_read_article = last_read_article
    progress.last_accessed_at = datetime.datetime.utcnow()
    if progress.status != 'concluido':
        progress.status = 'em_andamento'
        
    db.session.commit()
    return jsonify(success=True, message="Ponto de leitura salvo!")


@student_bp.route("/announcement/<int:announcement_id>/mark_seen", methods=["POST"])
@login_required
def mark_announcement_seen(announcement_id):
    existing = UserSeenAnnouncement.query.filter_by(user_id=current_user.id, announcement_id=announcement_id).first()
    if not existing:
        seen = UserSeenAnnouncement(user_id=current_user.id, announcement_id=announcement_id)
        db.session.add(seen)
        db.session.commit()
    return jsonify(success=True)


@student_bp.route("/law/<int:law_id>/notes", methods=["GET", "POST"])
@login_required
def handle_user_notes(law_id):
    if request.method == "GET":
        notes = UserNotes.query.filter_by(user_id=current_user.id, law_id=law_id).first()
        return jsonify(success=True, content=notes.content if notes else "")
    
    if request.method == "POST":
        content = request.json.get("content", "")
        notes = UserNotes.query.filter_by(user_id=current_user.id, law_id=law_id).first()
        if notes:
            notes.content = content
        else:
            notes = UserNotes(user_id=current_user.id, law_id=law_id, content=content)
            db.session.add(notes)
        db.session.commit()
        return jsonify(success=True, message="Anotações salvas!")


@student_bp.route("/law/<int:law_id>/comments", methods=["GET", "POST"])
@login_required
def handle_comments(law_id):
    if request.method == "GET":
        comments = UserComment.query.filter_by(user_id=current_user.id, law_id=law_id).all()
        return jsonify(success=True, comments=[{"id": c.id, "content": c.content, "anchor_paragraph_id": c.anchor_paragraph_id} for c in comments])

    if request.method == "POST":
        data = request.json
        new_comment = UserComment(
            content=data["content"],
            anchor_paragraph_id=data["anchor_paragraph_id"],
            user_id=current_user.id,
            law_id=law_id
        )
        db.session.add(new_comment)
        db.session.commit()
        return jsonify(success=True, comment={"id": new_comment.id, "content": new_comment.content, "anchor_paragraph_id": new_comment.anchor_paragraph_id}), 201


@student_bp.route("/comments/<int:comment_id>", methods=["PUT", "DELETE"])
@login_required
def handle_single_comment(comment_id):
    comment = UserComment.query.filter_by(id=comment_id, user_id=current_user.id).first_or_404()
    
    if request.method == "PUT":
        comment.content = request.json.get("content", "")
        db.session.commit()
        return jsonify(success=True, message="Anotação atualizada!", comment={"id": comment.id, "content": comment.content})

    if request.method == "DELETE":
        db.session.delete(comment)
        db.session.commit()
        return jsonify(success=True, message="Anotação excluída!")
