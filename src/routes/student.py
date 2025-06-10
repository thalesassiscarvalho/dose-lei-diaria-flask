# student.py ATUALIZADO E OTIMIZADO - VERSÃO COMPLETA

# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from src.models.user import db, Achievement, Announcement, User, UserSeenAnnouncement
from src.models.law import Law, Subject
from src.models.progress import UserProgress
from src.models.notes import UserNotes, UserLawMarkup # Importa o modelo atualizado
from src.models.comment import UserComment
import datetime
import logging

student_bp = Blueprint("student", __name__, url_prefix="/student")

@student_bp.route("/api/laws_for_subject/<int:subject_id>")
@login_required
def get_laws_for_subject(subject_id):
    """
    Endpoint de API para retornar os diplomas (leis principais) de uma matéria.
    """
    laws = Law.query.filter(
        Law.subject_id == subject_id,
        Law.parent_id.is_(None)
    ).order_by(Law.title).all()
    return jsonify([{"id": law.id, "title": law.title} for law in laws])

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
    """
    Renderiza a página principal do dashboard.
    A lista de leis agora é carregada dinamicamente via JavaScript.
    """
    subjects_for_filter = Subject.query.order_by(Subject.name).all()

    total_topics_count = Law.query.filter(Law.parent_id.isnot(None)).count()
    completed_count = UserProgress.query.filter_by(user_id=current_user.id, status='concluido').count()
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
                           subjects=subjects_for_filter,
                           progress_percentage=global_progress_percentage,
                           completed_count=completed_count,
                           total_laws=total_topics_count,
                           user_points=current_user.points,
                           user_achievements=current_user.achievements,
                           fixed_announcements=fixed_announcements,
                           non_fixed_announcements=non_fixed_announcements,
                           last_accessed_law=last_accessed_law)

@student_bp.route("/filter_laws")
@login_required
def filter_laws():
    """
    Endpoint da API que retorna a lista de legislações filtradas em JSON.
    """
    search_query = request.args.get("search", "")
    selected_subject_id_str = request.args.get("subject_id", "")
    selected_diploma_id_str = request.args.get("diploma_id", "")
    selected_status = request.args.get("status_filter", "")
    show_favorites = request.args.get("show_favorites", "false").lower() == 'true'

    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    progress_map = {p.law_id: p.status for p in user_progress_records}
    completed_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'concluido'}
    in_progress_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'em_andamento'}
    favorite_topic_ids = {law.id for law in current_user.favorite_laws if law.parent_id is not None}

    diplomas_query = Law.query.outerjoin(Subject).filter(Law.parent_id.is_(None)).options(
        joinedload(Law.children)
    )

    if search_query:
        search_term = f"%{search_query}%"
        diplomas_query = diplomas_query.filter(
            or_(Law.title.ilike(search_term), Subject.name.ilike(search_term), Law.children.any(Law.title.ilike(search_term)))
        )
    else:
        if selected_subject_id_str.isdigit():
            diplomas_query = diplomas_query.filter(Law.subject_id == int(selected_subject_id_str))
        if selected_diploma_id_str.isdigit():
            diplomas_query = diplomas_query.filter(Law.id == int(selected_diploma_id_str))
    
    all_diplomas = diplomas_query.order_by(Subject.name, Law.title).all()

    processed_diplomas = []
    for diploma in all_diplomas:
        children_to_display = []
        # A lógica para determinar quais filhos mostrar foi movida para dentro do loop
        for topic in diploma.children:
            is_completed = topic.id in completed_topic_ids
            is_in_progress = topic.id in in_progress_topic_ids
            is_not_read = not is_completed and not is_in_progress
            is_favorite = topic.id in favorite_topic_ids
            passes_status = (not selected_status or (selected_status == 'completed' and is_completed) or
                             (selected_status == 'in_progress' and is_in_progress) or (selected_status == 'not_read' and is_not_read))
            passes_favorite = not show_favorites or is_favorite
            
            # Adiciona o tópico se ele passar nos filtros de status e favoritos
            if passes_status and passes_favorite:
                children_to_display.append({
                    "id": topic.id, "title": topic.title, "is_completed": is_completed,
                    "is_in_progress": is_in_progress, "is_favorite": is_favorite
                })
        
        # O diploma só é incluído se tiver filhos que correspondam aos filtros (ou se for uma busca)
        if children_to_display or (search_query and any(search_query.lower() in child.title.lower() for child in diploma.children)):
             total_children = len(diploma.children)
             completed_children_count = sum(1 for child in diploma.children if child.id in completed_topic_ids)
             progress_percentage = (completed_children_count / total_children * 100) if total_children > 0 else 0
             processed_diplomas.append({
                 "title": diploma.title, "progress_percentage": progress_percentage,
                 "subject_name": diploma.subject.name if diploma.subject else "Sem Matéria",
                 "filtered_children": children_to_display
             })

    subjects_with_diplomas = {}
    for diploma_data in processed_diplomas:
        subject_name = diploma_data["subject_name"]
        if subject_name not in subjects_with_diplomas:
            subjects_with_diplomas[subject_name] = []
        subjects_with_diplomas[subject_name].append(diploma_data)

    return jsonify(subjects_with_diplomas=subjects_with_diplomas)


# <<< ALTERAÇÃO >>>: Rota view_law simplificada
@student_bp.route("/law/<int:law_id>")
@login_required
def view_law(law_id):
    law = Law.query.get_or_404(law_id)
    if law.parent_id is None:
        flash("Selecione um tópico de estudo específico para visualizar.", "info")
        return redirect(url_for('student.dashboard'))

    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    is_favorited = law in current_user.favorite_laws

    now = datetime.datetime.utcnow()
    if progress:
        progress.last_accessed_at = now
    else:
        progress = UserProgress(user_id=current_user.id, law_id=law_id, status='em_andamento', last_accessed_at=now)
        db.session.add(progress)
    db.session.commit()

    # A rota agora SEMPRE envia o conteúdo original da lei.
    content_to_display = law.content or ""

    return render_template("student/view_law.html",
                           law=law,
                           is_completed=(progress.status == 'concluido' if progress else False),
                           last_read_article=progress.last_read_article if progress else "",
                           is_favorited=is_favorited,
                           display_content=content_to_display)

@student_bp.route("/law/toggle_favorite/<int:law_id>", methods=["POST"])
@login_required
def toggle_favorite(law_id):
    law = Law.query.get_or_404(law_id)
    if law in current_user.favorite_laws:
        current_user.favorite_laws.remove(law)
        db.session.commit()
        return jsonify(success=True, favorited=False)
    else:
        current_user.favorite_laws.append(law)
        db.session.commit()
        return jsonify(success=True, favorited=True)

@student_bp.route("/law/mark_complete/<int:law_id>", methods=["POST"])
@login_required
def mark_complete(law_id):
    law = Law.query.get_or_404(law_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    should_award_points = not progress or not progress.completed_at
    if not progress or progress.status != 'concluido':
        if not progress:
            progress = UserProgress(user_id=current_user.id, law_id=law_id)
            db.session.add(progress)
        progress.status = 'concluido'
        if not progress.completed_at:
            progress.completed_at = datetime.datetime.utcnow()
        if should_award_points:
            points_to_award = 10
            current_user.points += points_to_award
            flash(f"Lei \"{law.title}\" marcada como concluída! Você ganhou {points_to_award} pontos.", "success")
        else:
            flash(f"Lei \"{law.title}\" marcada como concluída novamente!", "info")
        unlocked = check_and_award_achievements(current_user)
        if unlocked:
             flash(f"Conquistas desbloqueadas: {', '.join(unlocked)}!", "success")
        db.session.commit()
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
    db.session.commit()
    return jsonify(success=True, new_status='em_andamento')

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
    if not UserSeenAnnouncement.query.filter_by(user_id=current_user.id, announcement_id=announcement_id).first():
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

# <<< ROTA ANTIGA REMOVIDA >>>
# @student_bp.route("/law/<int:law_id>/save_markup", methods=['POST']) ...

# =====================================================================
# <<< INÍCIO: NOVOS ENDPOINTS DE API PARA MARCAÇÕES OTIMIZADAS >>>
# =====================================================================

@student_bp.route("/law/<int:law_id>/markups", methods=['GET', 'POST'])
@login_required
def handle_markups(law_id):
    """ Busca (GET) ou salva (POST) marcações de texto para uma lei. """
    if request.method == 'GET':
        markups = UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).all()
        return jsonify([
            {
                "id": m.id,
                "type": m.type,
                "start_container_path": m.start_container_path,
                "start_offset": m.start_offset,
                "end_container_path": m.end_container_path,
                "end_offset": m.end_offset
            } for m in markups
        ])

    if request.method == 'POST':
        data = request.get_json()
        required_keys = ['type', 'start_container_path', 'start_offset', 'end_container_path', 'end_offset']
        if not all(k in data for k in required_keys):
            return jsonify(success=False, error="Dados incompletos para a marcação."), 400

        new_markup = UserLawMarkup(
            user_id=current_user.id,
            law_id=law_id,
            type=data['type'],
            start_container_path=data['start_container_path'],
            start_offset=data['start_offset'],
            end_container_path=data['end_container_path'],
            end_offset=data['end_offset']
        )
        db.session.add(new_markup)
        db.session.commit()
        # Retorna o ID da marcação criada para que o frontend possa usá-lo
        return jsonify(success=True, markup={"id": new_markup.id}), 201

@student_bp.route("/markups/<int:markup_id>", methods=['DELETE'])
@login_required
def delete_markup(markup_id):
    """ Deleta uma marcação específica. """
    markup = UserLawMarkup.query.get_or_404(markup_id)
    if markup.user_id != current_user.id:
        return jsonify(success=False, error="Não autorizado"), 403
    
    db.session.delete(markup)
    db.session.commit()
    return jsonify(success=True, message="Marcação removida.")

# =====================================================================
# <<< FIM: NOVOS ENDPOINTS DE API >>>
# =====================================================================


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
