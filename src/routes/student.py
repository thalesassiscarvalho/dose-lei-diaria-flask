# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from src.models.user import db, Achievement, Announcement, User, UserSeenAnnouncement
from src.models.law import Law, Subject
from src.models.progress import UserProgress
from src.models.notes import UserNotes, UserLawMarkup
from src.models.comment import UserComment
import datetime
import logging

student_bp = Blueprint("student", __name__, url_prefix="/student")

# =====================================================================
# <<< NOVO ENDPOINT DE API PARA FILTRO EM CASCATA >>>
# =====================================================================
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
# =====================================================================

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

    # Apenas renderiza o template base. Os dados de leis serão buscados via API.
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


# =====================================================================
# <<< INÍCIO DA MODIFICAÇÃO PARA FILTROS HIERÁRQUICOS >>>
# =====================================================================
@student_bp.route("/filter_laws")
@login_required
def filter_laws():
    """
    Endpoint da API que retorna a lista de legislações filtradas em JSON.
    Modificado para aceitar filtros hierárquicos e busca independente.
    """
    search_query = request.args.get("search", "")

    # Filtros hierárquicos
    selected_subject_id_str = request.args.get("subject_id", "")
    selected_diploma_id_str = request.args.get("diploma_id", "") # Novo filtro para a Lei/Diploma
    selected_status = request.args.get("status_filter", "")

    # Filtros adicionais
    show_favorites_str = request.args.get("show_favorites", "false")
    show_favorites = show_favorites_str.lower() == 'true'

    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    progress_map = {p.law_id: p.status for p in user_progress_records}
    completed_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'concluido'}
    in_progress_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'em_andamento'}
    favorite_topic_ids = {law.id for law in current_user.favorite_laws if law.parent_id is not None}

    # Inicia a query base buscando os Diplomas (leis principais)
    diplomas_query = Law.query.outerjoin(Subject).filter(Law.parent_id.is_(None)).options(
        joinedload(Law.children)
    )

    # Lógica de filtragem: Busca por texto tem prioridade
    if search_query:
        search_term = f"%{search_query}%"
        # Busca no título do diploma, no nome da matéria ou nos títulos dos tópicos filhos
        diplomas_query = diplomas_query.filter(
            or_(
                Law.title.ilike(search_term),
                Subject.name.ilike(search_term),
                Law.children.any(Law.title.ilike(search_term))
            )
        )
    else:
        # Lógica de filtro hierárquico
        selected_subject_id = int(selected_subject_id_str) if selected_subject_id_str.isdigit() else None
        if selected_subject_id:
            diplomas_query = diplomas_query.filter(Law.subject_id == selected_subject_id)

        selected_diploma_id = int(selected_diploma_id_str) if selected_diploma_id_str.isdigit() else None
        if selected_diploma_id:
            diplomas_query = diplomas_query.filter(Law.id == selected_diploma_id)

    all_diplomas = diplomas_query.order_by(Subject.name, Law.title).all()

    processed_diplomas = []
    for diploma in all_diplomas:
        children_to_display = []
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
                children_to_display.append({
                    "id": topic.id,
                    "title": topic.title,
                    "is_completed": is_completed,
                    "is_in_progress": is_in_progress,
                    "is_favorite": is_favorite
                })

        is_hierarchical_filter_active = selected_subject_id_str or selected_diploma_id_str or selected_status or show_favorites

        children_final = children_to_display

        if search_query:
            children_final = [
                {
                    "id": t.id, "title": t.title,
                    "is_completed": t.id in completed_topic_ids,
                    "is_in_progress": t.id in in_progress_topic_ids,
                    "is_favorite": t.id in favorite_topic_ids
                } for t in diploma.children
            ]

        if children_final:
            total_children = len(diploma.children)
            completed_children_count = sum(1 for child in diploma.children if child.id in completed_topic_ids)
            progress_percentage = (completed_children_count / total_children * 100) if total_children > 0 else 0

            diploma_data = {
                "title": diploma.title,
                "progress_percentage": progress_percentage,
                "subject_name": diploma.subject.name if diploma.subject else "Sem Matéria",
                "filtered_children": children_final
            }
            processed_diplomas.append(diploma_data)

    subjects_with_diplomas = {}
    for diploma_data in processed_diplomas:
        subject_name = diploma_data["subject_name"]
        if subject_name not in subjects_with_diplomas:
            subjects_with_diplomas[subject_name] = []
        subjects_with_diplomas[subject_name].append(diploma_data)

    return jsonify(subjects_with_diplomas=subjects_with_diplomas)
# =====================================================================
# <<< FIM DA MODIFICAÇÃO >>>
# =====================================================================


# =====================================================================
# <<< INÍCIO: FUNÇÃO view_law MODIFICADA >>>
# =====================================================================
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

    # --- LÓGICA DE CONTEÚDO MELHORADA ---
    # 1. Busca o conteúdo personalizado que o usuário salvou
    user_markup = UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).first()

    # 2. Decide qual conteúdo exibir
    if user_markup:
        # Se houver marcação salva, use-a.
        content_to_display = user_markup.content
    else:
        # Senão, use o conteúdo original da lei.
        content_to_display = law.content

    # 3. Garante que nunca seja None, para evitar o erro no template.
    if content_to_display is None:
        content_to_display = ""

    return render_template("student/view_law.html",
                           law=law,
                           is_completed=(progress.status == 'concluido' if progress else False),
                           last_read_article=(progress.last_read_article if progress else None),
                           current_status=(progress.status if progress else 'nao_iniciado'),
                           is_favorited=is_favorited,
                           display_content=content_to_display) # <<< Passa a variável segura para o template
# =====================================================================
# <<< FIM: FUNÇÃO view_law MODIFICADA >>>
# =====================================================================


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

        try:
            db.session.commit()
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

# --- INÍCIO: NOVA ROTA PARA SALVAR MARCAÇÕES DE TEXTO ---
@student_bp.route("/law/<int:law_id>/save_markup", methods=['POST'])
@login_required
def save_law_markup(law_id):
    """
    Recebe o conteúdo HTML de uma lei com as marcações do usuário e salva no banco de dados.
    """
    # Garante que a lei para a qual estamos salvando existe.
    Law.query.get_or_404(law_id)

    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'success': False, 'error': 'Dados de conteúdo ausentes.'}), 400

        content = data.get('content')

        # Procura por uma marcação existente para este usuário e lei
        user_markup = UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).first()

        if user_markup:
            # Se já existe, apenas atualiza o conteúdo
            user_markup.content = content
        else:
            # Se não existe, cria um novo registro
            new_markup = UserLawMarkup(user_id=current_user.id, law_id=law_id, content=content)
            db.session.add(new_markup)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Marcações salvas com sucesso.'})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar marcações para law_id {law_id} para o usuário {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Um erro interno ocorreu ao salvar as marcações.'}), 500
# --- FIM: NOVA ROTA PARA SALVAR MARCAÇÕES DE TEXTO ---


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
