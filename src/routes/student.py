# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
# =====================================================================
# <<< INÍCIO DA IMPLEMENTAÇÃO: NOVOS IMPORTS >>>
# =====================================================================
# Adicionado 'date' e 'timedelta' para a lógica do Streak
from datetime import date, timedelta
from src.models.user import db, Achievement, Announcement, User, UserSeenAnnouncement, LawBanner, UserSeenLawBanner, StudyActivity
# =====================================================================
# <<< FIM DA IMPLEMENTAÇÃO >>>
# =====================================================================
from src.models.law import Law, Subject
from src.models.progress import UserProgress
from src.models.notes import UserNotes, UserLawMarkup
from src.models.comment import UserComment
import datetime
import logging

student_bp = Blueprint("student", __name__, url_prefix="/student")

# =====================================================================
# <<< ENDPOINTS DE API PARA FILTROS E BUSCA >>>
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

@student_bp.route("/api/topics_for_law/<int:law_id>")
@login_required
def get_topics_for_law(law_id):
    """
    Endpoint de API para retornar os tópicos (trechos/filhos) de uma lei (diploma).
    """
    parent_law = Law.query.filter_by(id=law_id, parent_id=None).first_or_404("Diploma não encontrado.")
    topics = Law.query.filter_by(parent_id=law_id).order_by(Law.id).all()
    return jsonify([{"id": topic.id, "title": topic.title} for topic in topics])

# =====================================================================
# <<< NOVO ENDPOINT DE API PARA BUSCA COM AUTOCOMPLETE >>>
# =====================================================================
@student_bp.route("/api/autocomplete_search")
@login_required
def autocomplete_search():
    query = request.args.get('q', '').strip()
    if len(query) < 3:
        return jsonify(results=[])

    search_term = f"%{query}%"
    results = []
    limit = 5 # Limite de resultados por categoria

    # Buscar em Tópicos/Artigos
    topics = Law.query.filter(
        Law.parent_id.isnot(None),
        Law.title.ilike(search_term)
    ).limit(limit).all()
    for topic in topics:
        results.append({
            "title": topic.title,
            "category": "Artigo/Tópico",
            "url": url_for('student.view_law', law_id=topic.id)
        })

    # Buscar em Leis/Diplomas
    laws = Law.query.filter(
        Law.parent_id.is_(None),
        Law.title.ilike(search_term)
    ).limit(limit).all()
    for law in laws:
        # Para uma lei, levamos ao dashboard com o filtro aplicado
        results.append({
            "title": law.title,
            "category": "Lei",
            "url": url_for('student.dashboard', diploma_id=law.id, subject_id=law.subject_id)
        })

    # Buscar em Matérias
    subjects = Subject.query.filter(Subject.name.ilike(search_term)).limit(limit).all()
    for subject in subjects:
        results.append({
            "title": subject.name,
            "category": "Matéria",
            "url": url_for('student.dashboard', subject_id=subject.id)
        })

    # Remove duplicados com base no título e categoria, mantendo a ordem
    unique_results = []
    seen = set()
    for r in results:
        identifier = (r['title'], r['category'])
        if identifier not in seen:
            unique_results.append(r)
            seen.add(identifier)

    return jsonify(results=unique_results[:7]) # Retorna no máximo 7 resultados únicos
# =====================================================================


# --- INÍCIO DA ALTERAÇÃO: ANIMAÇÃO DE CONQUISTA (1/2) ---
# A função agora retorna os objetos de conquista completos para que possamos usar seus detalhes na animação.
def check_and_award_achievements(user):
    """Verifica e concede conquistas ao usuário."""
    unlocked_achievements_objects = []  # Alterado de 'names' para 'objects'
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
                unlocked_achievements_objects.append(achievement)  # Adiciona o objeto completo

    return unlocked_achievements_objects  # Retorna a lista de objetos
# --- FIM DA ALTERAÇÃO: ANIMAÇÃO DE CONQUISTA (1/2) ---

# =====================================================================
# <<< INÍCIO DA IMPLEMENTAÇÃO: LÓGICA DO STREAK DE ESTUDOS >>>
# =====================================================================
def _record_study_activity(user: User):
    """Registra que o usuário estudou hoje. Cria um registro em StudyActivity se ainda não houver um para o dia."""
    today = date.today()
    # Verifica se já existe um registro para o usuário no dia de hoje
    activity_exists = user.study_activities.filter(StudyActivity.study_date == today).first()

    if not activity_exists:
        try:
            new_activity = StudyActivity(user_id=user.id, study_date=today)
            db.session.add(new_activity)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao registrar atividade de estudo para o usuário {user.id}: {e}")

def _calculate_user_streak(user: User) -> int:
    """Calcula a sequência de dias de estudo consecutivos do usuário."""
    activities = user.study_activities.order_by(StudyActivity.study_date.desc()).all()
    
    if not activities:
        return 0

    today = date.today()
    yesterday = today - timedelta(days=1)
    
    latest_activity_date = activities[0].study_date
    
    # Se a última atividade não foi hoje nem ontem, a sequência foi quebrada.
    if latest_activity_date not in [today, yesterday]:
        return 0

    streak_count = 1
    current_date = latest_activity_date

    # Itera sobre as atividades restantes para contar os dias consecutivos
    for activity in activities[1:]:
        expected_previous_day = current_date - timedelta(days=1)
        if activity.study_date == expected_previous_day:
            streak_count += 1
            current_date = activity.study_date
        else:
            # A sequência foi interrompida
            break
            
    return streak_count
# =====================================================================
# <<< FIM DA IMPLEMENTAÇÃO >>>
# =====================================================================

@student_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Renderiza a página principal do dashboard.
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
    
    user_streak = _calculate_user_streak(current_user)

    # --- INÍCIO: 3ª MELHORIA - LÓGICA PARA AGRUPAR FAVORITOS POR MATÉRIA ---
    favorites_by_subject = {}
    
    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    completed_topic_ids = {p.law_id for p in user_progress_records if p.status == 'concluido'}
    
    # Garante que a relação 'parent' e 'subject' sejam carregadas para evitar múltiplas queries
    favorite_topics_query = current_user.favorite_laws.options(
        joinedload(Law.parent).joinedload(Law.subject)
    ).filter(Law.parent_id.isnot(None)).all()

    # Primeiro, agrupa os tópicos por Lei (parent)
    grouped_by_law = {}
    for topic in favorite_topics_query:
        if topic.parent:
            if topic.parent not in grouped_by_law:
                grouped_by_law[topic.parent] = []
            grouped_by_law[topic.parent].append(topic)
    
    # Agora, cria os cards de Lei e os agrupa por Matéria
    for law, topics in grouped_by_law.items():
        subject = law.subject
        if not subject:
            continue

        if subject not in favorites_by_subject:
            favorites_by_subject[subject] = []
            
        completed_in_group = sum(1 for topic in topics if topic.id in completed_topic_ids)
        total_in_group = len(topics)
        progress_percentage = (completed_in_group / total_in_group * 100) if total_in_group > 0 else 0
        
        in_progress_topic_ids = {p.law_id for p in user_progress_records if p.status == 'em_andamento'}
        topic_details_list = []
        for topic in sorted(topics, key=lambda t: t.id):
            topic_details_list.append({
                "id": topic.id,
                "title": topic.title,
                "is_completed": topic.id in completed_topic_ids,
                "is_in_progress": topic.id in in_progress_topic_ids,
            })

        favorites_by_subject[subject].append({
            "parent": law,
            "topics": topic_details_list,
            "progress": progress_percentage
        })

    # --- FIM DA LÓGICA ---

    return render_template("student/dashboard.html",
                           subjects=subjects_for_filter,
                           progress_percentage=global_progress_percentage,
                           completed_count=completed_count,
                           total_laws=total_topics_count,
                           user_points=current_user.points,
                           user_achievements=current_user.achievements,
                           fixed_announcements=fixed_announcements,
                           non_fixed_announcements=non_fixed_announcements,
                           last_accessed_law=last_accessed_law,
                           user_streak=user_streak,
                           favorites_by_subject=favorites_by_subject  # Passa a nova estrutura
                           )


@student_bp.route("/filter_laws")
@login_required
def filter_laws():
    """
    Endpoint da API que retorna a lista de legislações filtradas em JSON.
    """
    selected_subject_id_str = request.args.get("subject_id", "")
    selected_diploma_id_str = request.args.get("diploma_id", "")
    selected_status = request.args.get("status_filter", "")
    selected_topic_id_str = request.args.get("topic_id", "")

    show_favorites_str = request.args.get("show_favorites", "false")
    show_favorites = show_favorites_str.lower() == 'true'

    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    progress_map = {p.law_id: p.status for p in user_progress_records}
    completed_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'concluido'}
    in_progress_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'em_andamento'}
    favorite_topic_ids = {law.id for law in current_user.favorite_laws if law.parent_id is not None}

    diplomas_query = Law.query.outerjoin(Subject).filter(Law.parent_id.is_(None)).options(
        joinedload(Law.children)
    )

    selected_subject_id = int(selected_subject_id_str) if selected_subject_id_str.isdigit() else None
    if selected_subject_id:
        diplomas_query = diplomas_query.filter(Law.subject_id == selected_subject_id)

    selected_diploma_id = int(selected_diploma_id_str) if selected_diploma_id_str.isdigit() else None
    if selected_diploma_id:
        diplomas_query = diplomas_query.filter(Law.id == selected_diploma_id)

    all_diplomas = diplomas_query.order_by(Subject.name, Law.title).all()
    selected_topic_id = int(selected_topic_id_str) if selected_topic_id_str.isdigit() else None

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
            
            passes_topic = (not selected_topic_id or topic.id == selected_topic_id)
            passes_favorite = not show_favorites or is_favorite

            if passes_status and passes_topic and passes_favorite:
                children_to_display.append({
                    "id": topic.id, "title": topic.title,
                    "is_completed": is_completed, "is_in_progress": is_in_progress,
                    "is_favorite": is_favorite
                })

        if children_to_display:
            total_children = len(diploma.children)
            completed_children_count = sum(1 for child in diploma.children if child.id in completed_topic_ids)
            progress_percentage = (completed_children_count / total_children * 100) if total_children > 0 else 0

            diploma_data = {
                "title": diploma.title,
                "progress_percentage": progress_percentage,
                "subject_name": diploma.subject.name if diploma.subject else "Sem Matéria",
                "filtered_children": children_to_display
            }
            processed_diplomas.append(diploma_data)

    subjects_with_diplomas = {}
    for diploma_data in processed_diplomas:
        subject_name = diploma_data["subject_name"]
        if subject_name not in subjects_with_diplomas:
            subjects_with_diplomas[subject_name] = []
        subjects_with_diplomas[subject_name].append(diploma_data)

    return jsonify(subjects_with_diplomas=subjects_with_diplomas)


@student_bp.route("/law/<int:law_id>")
@login_required
def view_law(law_id):
    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: OTIMIZAR CONSULTA E VERIFICAR BANNER >>>
    # =====================================================================
    # Otimiza a consulta para carregar a lei e seu banner (se existir) de uma vez
    law = Law.query.options(joinedload(Law.banner)).get_or_404(law_id)
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO >>>
    # =====================================================================
    if law.parent_id is None:
        flash("Selecione um tópico de estudo específico para visualizar.", "info")
        return redirect(url_for('student.dashboard'))
        
    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: REGISTRO DA ATIVIDADE DE ESTUDO >>>
    # =====================================================================
    _record_study_activity(current_user)
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO >>>
    # =====================================================================

    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    user_markup = UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    is_favorited = law in current_user.favorite_laws

    now = datetime.datetime.utcnow()
    if progress:
        progress.last_accessed_at = now
    else:
        progress = UserProgress(user_id=current_user.id, law_id=law_id, status='em_andamento', last_accessed_at=now)
        db.session.add(progress)
    db.session.commit()

    content_to_display = user_markup.content if user_markup else law.content
    if content_to_display is None: content_to_display = ""

    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: LÓGICA DE EXIBIÇÃO DO BANNER >>>
    # =====================================================================
    banner_to_show = None
    if law.banner:
        # Verifica se já existe um registro do usuário vendo ESTA VERSÃO do banner
        seen_banner_record = UserSeenLawBanner.query.filter_by(
            user_id=current_user.id,
            law_id=law_id,
            seen_at_timestamp=law.banner.last_updated
        ).first()

        # Se não houver registro, o banner deve ser mostrado
        if not seen_banner_record:
            banner_to_show = law.banner
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO >>>
    # =====================================================================

    return render_template("student/view_law.html",
                           law=law, is_completed=(progress.status == 'concluido'),
                           last_read_article=progress.last_read_article, current_status=progress.status,
                           is_favorited=is_favorited, display_content=content_to_display,
                           # ==================================================
                           # <<< INÍCIO DA IMPLEMENTAÇÃO: PASSAR BANNER PARA O TEMPLATE >>>
                           # ==================================================
                           banner_to_show=banner_to_show
                           # ==================================================
                           # <<< FIM DA IMPLEMENTAÇÃO >>>
                           # ==================================================
                           )


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

# --- INÍCIO DA ALTERAÇÃO: ANIMAÇÃO DE CONQUISTA (2/2) ---
# A rota foi modificada para retornar JSON em vez de redirecionar.
# Isso permite que o frontend (JavaScript) receba os dados e dispare a animação.
@student_bp.route("/law/mark_complete/<int:law_id>", methods=["POST"])
@login_required
def mark_complete(law_id):
    law = Law.query.get_or_404(law_id)
    progress = UserProgress.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    should_award_points = not progress or not progress.completed_at

    unlocked_achievements = []

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
        
        # A função 'check_and_award_achievements' agora retorna os objetos completos.
        unlocked_achievements_obj = check_and_award_achievements(current_user)
        
        # Prepara os dados das conquistas para serem enviados como JSON.
        if unlocked_achievements_obj:
            flash(f"Conquistas desbloqueadas: {', '.join([ach.name for ach in unlocked_achievements_obj])}!", "success")
            unlocked_achievements = [
                {"name": ach.name, "description": ach.description, "icon": ach.icon}
                for ach in unlocked_achievements_obj
            ]

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Mantemos o flash de erro para o caso de o JS falhar e a página recarregar
            flash(f"Erro ao salvar progresso: {e}", "danger")
            logging.error(f"Erro ao salvar progresso para law_id {law_id}: {e}")
            return jsonify(success=False, error=str(e)), 500
    else:
        flash(f"Você já marcou \"{law.title}\" como concluída.", "info")

    # Retorna uma resposta JSON com os dados das conquistas desbloqueadas.
    return jsonify(
        success=True,
        unlocked_achievements=unlocked_achievements
    )
# --- FIM DA ALTERAÇÃO: ANIMAÇÃO DE CONQUISTA (2/2) ---


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

# =====================================================================
# <<< INÍCIO DA IMPLEMENTAÇÃO: NOVA ROTA PARA MARCAR BANNER COMO VISTO >>>
# =====================================================================
@student_bp.route("/law/<int:law_id>/mark_banner_seen", methods=["POST"])
@login_required
def mark_banner_seen(law_id):
    """
    Endpoint de API para o aluno marcar o banner de uma lei como visto.
    """
    law = Law.query.options(joinedload(Law.banner)).get_or_404(law_id)
    
    if not law.banner:
        return jsonify(success=False, error="Banner não encontrado."), 404

    banner_timestamp = law.banner.last_updated

    existing_seen = UserSeenLawBanner.query.filter_by(
        user_id=current_user.id,
        law_id=law.id,
        seen_at_timestamp=banner_timestamp
    ).first()

    if not existing_seen:
        seen_record = UserSeenLawBanner(
            user_id=current_user.id,
            law_id=law.id,
            seen_at_timestamp=banner_timestamp
        )
        db.session.add(seen_record)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao salvar 'seen banner' para user {current_user.id} e law {law_id}: {e}")
            return jsonify(success=False, error="Erro ao salvar no banco de dados."), 500

    return jsonify(success=True)
# =====================================================================
# <<< FIM DA IMPLEMENTAÇÃO >>>
# =====================================================================

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

@student_bp.route("/law/<int:law_id>/save_markup", methods=['POST'])
@login_required
def save_law_markup(law_id):
    Law.query.get_or_404(law_id)
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'success': False, 'error': 'Dados de conteúdo ausentes.'}), 400
        content = data.get('content')
        user_markup = UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).first()
        if user_markup:
            user_markup.content = content
        else:
            new_markup = UserLawMarkup(user_id=current_user.id, law_id=law_id, content=content)
            db.session.add(new_markup)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Marcações salvas com sucesso.'})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar marcações para law_id {law_id} para o usuário {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Um erro interno ocorreu ao salvar as marcações.'}), 500

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

# =====================================================================
# <<< NOVA ROTA PARA RESTAURAR A LEI >>>
# =====================================================================
@student_bp.route("/law/<int:law_id>/restore", methods=['POST'])
@login_required
def restore_law_to_original(law_id):
    """
    Restaura a lei para seu estado original para o usuário,
    removendo marcações e comentários.
    """
    Law.query.get_or_404(law_id)
    
    try:
        # Deleta as marcações (highlights, bold, etc.) do usuário para esta lei
        UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).delete()

        # Deleta os comentários de parágrafo do usuário para esta lei
        UserComment.query.filter_by(user_id=current_user.id, law_id=law_id).delete()
        
        # Confirma as alterações no banco de dados
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Lei restaurada com sucesso.'})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao restaurar a lei {law_id} para o usuário {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Um erro interno ocorreu ao restaurar a lei.'}), 500
