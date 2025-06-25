# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, func, Date
from sqlalchemy.orm import joinedload
from datetime import date, timedelta
import datetime
import bleach
from bleach.css_sanitizer import CSSSanitizer
from src.extensions import db
# =====================================================================
# <<< INÍCIO DA ALTERAÇÃO 1/3: IMPORTANDO OS NOVOS MODELOS >>>
# =====================================================================
from src.models.user import Achievement, Announcement, User, UserSeenAnnouncement, LawBanner, UserSeenLawBanner, StudyActivity, TodoItem, CommunityContribution, CommunityComment
# =====================================================================
# <<< FIM DA ALTERAÇÃO 1/3 >>>
# =====================================================================
from src.models.law import Law, Subject
from src.models.progress import UserProgress
from src.models.notes import UserNotes, UserLawMarkup
from src.models.comment import UserComment
from src.models.concurso import Concurso
from src.models.study import StudySession
import logging
import pytz

student_bp = Blueprint("student", __name__, url_prefix="/student")

# Definição das regras de sanitização
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 
    'ul', 'ol', 'li', 'a', 'blockquote',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'span', 'div'
]
ALLOWED_ATTRIBUTES = {
    '*': ['style', 'class', 'title'],
    'a': ['href', 'title', 'target']
}
ALLOWED_STYLES = [
    'color', 'background-color', 'font-weight', 'font-style', 'text-decoration',
    'text-align', 'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'border', 'border-left'
]
css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)


def get_user_permissions():
    """
    Verifica as permissões do usuário logado e retorna os IDs do conteúdo que ele pode ver.
    Retorna None para cada tipo de ID se o usuário puder ver tudo.
    """
    if current_user.is_authenticated and not current_user.can_see_all_concursos:
        user_concursos = current_user.associated_concursos.all()
        allowed_concurso_ids = {c.id for c in user_concursos}

        if not allowed_concurso_ids:
            return {-1}, {-1}, {-1}

        laws_in_allowed_concursos = db.session.query(Law.id, Law.parent_id, Law.subject_id)\
            .join(Law.concursos)\
            .filter(Concurso.id.in_(allowed_concurso_ids)).all()
        
        allowed_law_ids = {row.id for row in laws_in_allowed_concursos}
        allowed_law_ids.update({row.parent_id for row in laws_in_allowed_concursos if row.parent_id})
        
        allowed_subject_ids = {row.subject_id for row in laws_in_allowed_concursos if row.subject_id}

        return allowed_concurso_ids, allowed_law_ids, allowed_subject_ids

    return None, None, None


def _humanize_time_delta(dt):
    if not dt:
        return ""
    now = datetime.datetime.utcnow()
    delta = now - dt
    
    seconds = delta.total_seconds()
    days = delta.days
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        if days == 1:
            return "1 dia atrás"
        return f"{days} dias atrás"
    if hours > 0:
        if hours == 1:
            return "1 hora atrás"
        return f"{int(hours)} horas atrás"
    if minutes > 0:
        if minutes == 1:
            return "1 minuto atrás"
        return f"{int(minutes)} minutos atrás"
    return "agora mesmo"

def _format_duration(total_seconds):
    if not isinstance(total_seconds, (int, float)) or total_seconds < 0:
        total_seconds = 0
        
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)

    if hours == 0 and minutes == 0:
        return "0 minutos"

    parts = []
    if hours > 0:
        parts.append(f"{hours} hora{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minuto{'s' if minutes > 1 else ''}")
    
    return " e ".join(parts)

LEVELS = [
    {"name": "Novato", "min_points": 0, "icon": "fas fa-seedling"},
    {"name": "Primeiro Passo", "min_points": 10, "icon": "fas fa-shoe-prints"},
    {"name": "Estudante Dedicado", "min_points": 50, "icon": "fas fa-book-reader"},
    {"name": "Leitor de Leis", "min_points": 100, "icon": "fas fa-glasses"},
    {"name": "Operador do Saber", "min_points": 150, "icon": "fas fa-cogs"},
    {"name": "Mestre em Formação", "min_points": 250, "icon": "fas fa-graduation-cap"},
    {"name": "Mestre das Normas", "min_points": 400, "icon": "fas fa-balance-scale"},
    {"name": "Guardião das Leis", "min_points": 700, "icon": "fas fa-gavel"},
    {"name": "Mentor da Lei", "min_points": 1000, "icon": "fas fa-chalkboard-teacher"},
    {"name": "Uma Lenda", "min_points": 1500, "icon": "fas fa-crown"}
]

def get_user_level_info(points):
    user_level = LEVELS[0]
    next_level = None

    for i, level in enumerate(LEVELS):
        if points >= level["min_points"]:
            user_level = level
            if i + 1 < len(LEVELS):
                next_level = LEVELS[i + 1]
            else:
                next_level = None
        else:
            break
    
    if not next_level:
        return {
            "current_level": user_level,
            "next_level": None,
            "progress_percent": 100,
            "points_to_next": 0
        }

    level_start_points = user_level["min_points"]
    points_for_next_level = next_level["min_points"]
    
    points_in_current_level = points - level_start_points
    points_needed_for_level = points_for_next_level - level_start_points
    
    progress_percent = (points_in_current_level / points_needed_for_level * 100) if points_needed_for_level > 0 else 0
    
    return {
        "current_level": user_level,
        "next_level": next_level,
        "progress_percent": progress_percent,
        "points_to_next": points_for_next_level - points
    }

@student_bp.route("/api/laws_for_subject/<int:subject_id>")
@login_required
def get_laws_for_subject(subject_id):
    _, allowed_law_ids, _ = get_user_permissions()
    
    laws_query = Law.query.filter(
        Law.subject_id == subject_id,
        Law.parent_id.is_(None)
    )

    if allowed_law_ids is not None:
        laws_query = laws_query.filter(Law.id.in_(allowed_law_ids))
    
    laws = laws_query.order_by(Law.title).all()
    return jsonify([{"id": law.id, "title": law.title} for law in laws])

@student_bp.route("/api/topics_for_law/<int:law_id>")
@login_required
def get_topics_for_law(law_id):
    _, allowed_law_ids, _ = get_user_permissions()
    
    if allowed_law_ids is not None and law_id not in allowed_law_ids:
        return jsonify(error="Acesso não permitido a este diploma."), 403

    topics_query = Law.query.filter_by(parent_id=law_id)

    if allowed_law_ids is not None:
        topics_query = topics_query.filter(Law.id.in_(allowed_law_ids))
    
    topics = topics_query.order_by(Law.id).all()
    return jsonify([{"id": topic.id, "title": topic.title} for topic in topics])

@student_bp.route("/api/autocomplete_search")
@login_required
def autocomplete_search():
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all') 

    if len(query) < 3:
        return jsonify(results=[])

    allowed_concurso_ids, allowed_law_ids, allowed_subject_ids = get_user_permissions()

    search_term = f"%{query}%"
    results = []
    limit = 7

    if search_type == 'topic' or search_type == 'all':
        topics_query = Law.query.filter(
            Law.parent_id.isnot(None),
            or_(Law.title.ilike(search_term), Law.content.ilike(search_term))
        ).options(joinedload(Law.parent))
        
        if allowed_law_ids is not None:
            topics_query = topics_query.filter(Law.id.in_(allowed_law_ids))

        for topic in topics_query.limit(limit).all():
            parent_title = topic.parent.title if topic.parent else "Tópico"
            results.append({
                "id": topic.id,
                "title": f"{parent_title} - {topic.title}",
                "category": "Tópico de Lei",
                "url": url_for('student.view_law', law_id=topic.id)
            })

    if search_type != 'topic':
        if search_type == 'all':
            limit = 5 

        laws_query = Law.query.filter(
            Law.parent_id.is_(None),
            Law.title.ilike(search_term)
        )
        subjects_query = Subject.query.filter(Subject.name.ilike(search_term))

        if allowed_law_ids is not None:
            laws_query = laws_query.filter(Law.id.in_(allowed_law_ids))
        if allowed_subject_ids is not None:
            subjects_query = subjects_query.filter(Subject.id.in_(allowed_subject_ids))

        for law in laws_query.limit(limit).all():
            results.append({
                "id": law.id,
                "title": law.title,
                "category": "Diploma Legal",
                "url": url_for('student.dashboard', diploma_id=law.id, subject_id=law.subject_id)
            })

        for subject in subjects_query.limit(limit).all():
            results.append({
                "id": subject.id,
                "title": subject.name,
                "category": "Matéria",
                "url": url_for('student.dashboard', subject_id=subject.id)
            })

    unique_results = []
    seen_ids = set()
    for r in results:
        if r['id'] not in seen_ids:
            unique_results.append(r)
            seen_ids.add(r['id'])

    return jsonify(results=unique_results[:10])


@student_bp.route("/api/concurso/<int:concurso_id>/details")
@login_required
def get_concurso_details(concurso_id):
    concurso = Concurso.query.get_or_404(concurso_id)
    return jsonify(
        success=True,
        edital_url=concurso.edital_verticalizado_url
    )

def check_and_award_achievements(user):
    unlocked_achievements_objects = []
    all_achievements = Achievement.query.order_by(Achievement.points_threshold).all()
    user_achievement_ids = {a.id for a in user.achievements}

    for achievement in all_achievements:
        if achievement.id not in user_achievement_ids:
            if achievement.points_threshold is not None and user.points >= achievement.points_threshold:
                user.achievements.append(achievement)
                unlocked_achievements_objects.append(achievement)

    return unlocked_achievements_objects

def _record_study_activity(user: User):
    today = date.today()
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
    activities = user.study_activities.order_by(StudyActivity.study_date.desc()).all()
    
    if not activities:
        return 0

    today = date.today()
    yesterday = today - timedelta(days=1)
    
    latest_activity_date = activities[0].study_date
    
    if latest_activity_date not in [today, yesterday]:
        return 0

    streak_count = 1
    current_date = latest_activity_date

    for activity in activities[1:]:
        expected_previous_day = current_date - timedelta(days=1)
        if activity.study_date == expected_previous_day:
            streak_count += 1
            current_date = activity.study_date
        else:
            break
            
    return streak_count

@student_bp.route("/dashboard")
@login_required
def dashboard():
    allowed_concurso_ids, allowed_law_ids, allowed_subject_ids = get_user_permissions()

    subjects_query = Subject.query
    concursos_query = Concurso.query
    total_topics_query = Law.query.filter(Law.parent_id.isnot(None))
    recent_progresses_query = UserProgress.query.join(UserProgress.law).filter(
        UserProgress.user_id == current_user.id,
        UserProgress.last_accessed_at.isnot(None),
        Law.parent_id.isnot(None)
    )
    favorite_topics_query = current_user.favorite_laws.options(
        joinedload(Law.parent).joinedload(Law.subject)
    ).filter(Law.parent_id.isnot(None))
    
    if allowed_law_ids is not None:
        subjects_query = subjects_query.filter(Subject.id.in_(allowed_subject_ids))
        concursos_query = concursos_query.filter(Concurso.id.in_(allowed_concurso_ids))
        total_topics_query = total_topics_query.filter(Law.id.in_(allowed_law_ids))
        recent_progresses_query = recent_progresses_query.filter(UserProgress.law_id.in_(allowed_law_ids))
        favorite_topics_query = favorite_topics_query.filter(Law.id.in_(allowed_law_ids))

    subjects_for_filter = subjects_query.order_by(Subject.name).all()
    concursos_for_filter = concursos_query.order_by(Concurso.name).all()
    total_topics_count = total_topics_query.count()
    
    completed_count = UserProgress.query.filter_by(user_id=current_user.id, status='concluido')
    if allowed_law_ids is not None:
        completed_count = completed_count.filter(UserProgress.law_id.in_(allowed_law_ids))
    completed_count = completed_count.count()

    global_progress_percentage = (completed_count / total_topics_count * 100) if total_topics_count > 0 else 0

    recent_progresses = recent_progresses_query.options(
        joinedload(UserProgress.law).joinedload(Law.parent)
    ).order_by(UserProgress.last_accessed_at.desc()).limit(3).all()

    recent_activities = []
    for progress in recent_progresses:
        recent_activities.append({
            "law": progress.law,
            "time_ago": _humanize_time_delta(progress.last_accessed_at)
        })

    fixed_announcements = Announcement.query.filter_by(is_active=True, is_fixed=True).order_by(Announcement.created_at.desc()).all()
    seen_announcement_ids = db.session.query(UserSeenAnnouncement.announcement_id).filter_by(user_id=current_user.id).scalar_subquery()
    non_fixed_announcements = Announcement.query.filter(
        Announcement.is_active==True, Announcement.is_fixed==False, Announcement.id.notin_(seen_announcement_ids)
    ).order_by(Announcement.created_at.desc()).all()
    
    user_streak = _calculate_user_streak(current_user)

    favorites_by_subject = {}
    
    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    completed_topic_ids = {p.law_id for p in user_progress_records if p.status == 'concluido'}
    
    favorite_topics = favorite_topics_query.all()

    grouped_by_law = {}
    for topic in favorite_topics:
        if topic.parent:
            if topic.parent not in grouped_by_law:
                grouped_by_law[topic.parent] = []
            grouped_by_law[topic.parent].append(topic)
    
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

    level_info = get_user_level_info(current_user.points)
    todo_items = current_user.todo_items.order_by(TodoItem.is_completed.asc(), TodoItem.created_at.desc()).all()
    
    default_concurso_id = current_user.default_concurso_id

    total_study_seconds = db.session.query(func.sum(StudySession.duration_seconds))\
                                    .filter_by(user_id=current_user.id).scalar() or 0
    formatted_total_study = _format_duration(total_study_seconds)

    one_week_ago = datetime.datetime.utcnow() - timedelta(days=7)
    weekly_study_seconds = db.session.query(func.sum(StudySession.duration_seconds))\
                                     .filter_by(user_id=current_user.id)\
                                     .filter(StudySession.recorded_at >= one_week_ago).scalar() or 0
    formatted_weekly_study = _format_duration(weekly_study_seconds)

    try:
        brazil_tz = pytz.timezone('America/Sao_Paulo')
        now_in_brazil = datetime.datetime.utcnow().astimezone(brazil_tz)
        today_start_in_brazil = now_in_brazil.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start_in_brazil.astimezone(pytz.utc)
    except pytz.UnknownTimeZoneError:
        logging.warning("Fuso horário 'America/Sao_Paulo' não encontrado. Usando UTC como padrão.")
        today_start_utc = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    daily_study_seconds = db.session.query(func.sum(StudySession.duration_seconds))\
                                    .filter_by(user_id=current_user.id)\
                                    .filter(StudySession.recorded_at >= today_start_utc).scalar() or 0
    formatted_daily_study = _format_duration(daily_study_seconds)
    
    weekly_activity_data = []
    days_of_week_br = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    today_in_brazil = now_in_brazil.date()

    start_date_of_week = today_in_brazil - timedelta(days=6)
    start_date_utc = datetime.datetime.combine(start_date_of_week, datetime.time.min).astimezone(brazil_tz).astimezone(pytz.utc)
    
    study_sessions_week = db.session.query(
        func.cast(func.timezone('America/Sao_Paulo', func.timezone('UTC', StudySession.recorded_at)), Date).label('study_date'),
        func.sum(StudySession.duration_seconds).label('total_seconds')
    ).filter(
        StudySession.user_id == current_user.id,
        StudySession.recorded_at >= start_date_utc
    ).group_by('study_date').all()
    
    study_by_date = {session.study_date: session.total_seconds for session in study_sessions_week}

    for i in range(7):
        current_day = today_in_brazil - timedelta(days=6-i)
        duration_minutes = round((study_by_date.get(current_day, 0) or 0) / 60)
        
        day_label = "Hoje" if current_day == today_in_brazil else days_of_week_br[current_day.weekday()]
        
        weekly_activity_data.append({
            "label": day_label,
            "minutes": duration_minutes
        })

    study_by_subject_data = db.session.query(
        Subject.name,
        func.sum(StudySession.duration_seconds).label('total_duration_seconds')
    ).join(StudySession, StudySession.subject_id == Subject.id)\
     .filter(StudySession.user_id == current_user.id)\
     .group_by(Subject.name)\
     .order_by(func.sum(StudySession.duration_seconds).desc())\
     .all()
    
    most_studied_subject = None
    study_data_for_chart = []
    if study_by_subject_data:
        most_studied_subject = {
            'name': study_by_subject_data[0][0],
            'duration': _format_duration(study_by_subject_data[0][1])
        }
        for subject_name, duration_seconds in study_by_subject_data:
            study_data_for_chart.append({
                'name': subject_name,
                'duration_seconds': duration_seconds
            })

    return render_template("student/dashboard.html",
                           subjects=subjects_for_filter,
                           concursos=concursos_for_filter,
                           progress_percentage=global_progress_percentage,
                           completed_count=completed_count,
                           total_laws=total_topics_count,
                           user_points=current_user.points,
                           user_achievements=current_user.achievements,
                           fixed_announcements=fixed_announcements,
                           non_fixed_announcements=non_fixed_announcements,
                           recent_activities=recent_activities,
                           user_streak=user_streak,
                           favorites_by_subject=favorites_by_subject,
                           level_info=level_info,
                           todo_items=todo_items,
                           custom_favorite_title=current_user.favorite_label,
                           default_concurso_id=default_concurso_id,
                           total_study_formatted=formatted_total_study,
                           weekly_study_formatted=formatted_weekly_study,
                           daily_study_formatted=formatted_daily_study,
                           most_studied_subject=most_studied_subject,
                           study_data_for_chart=study_data_for_chart,
                           weekly_activity_data=weekly_activity_data
                           )


@student_bp.route("/filter_laws")
@login_required
def filter_laws():
    selected_concurso_id_str = request.args.get("concurso_id", "")
    selected_subject_id_str = request.args.get("subject_id", "")
    selected_diploma_id_str = request.args.get("diploma_id", "")
    selected_status = request.args.get("status_filter", "")
    selected_topic_id_str = request.args.get("topic_id", "")
    show_favorites = request.args.get("show_favorites", "false").lower() == 'true'

    allowed_concurso_ids, allowed_law_ids, _ = get_user_permissions()

    user_progress_records = UserProgress.query.filter_by(user_id=current_user.id).all()
    progress_map = {p.law_id: p.status for p in user_progress_records}
    completed_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'concluido'}
    in_progress_topic_ids = {law_id for law_id, status in progress_map.items() if status == 'em_andamento'}
    favorite_topic_ids = {law.id for law in current_user.favorite_laws if law.parent_id is not None}

    diplomas_query = Law.query.filter(Law.parent_id.is_(None)).options(joinedload(Law.children), joinedload(Law.subject))
    
    if allowed_law_ids is not None:
        diplomas_query = diplomas_query.filter(Law.id.in_(allowed_law_ids))

    topic_ids_to_show = None

    if selected_concurso_id_str.isdigit():
        concurso = Concurso.query.get(int(selected_concurso_id_str))
        if concurso and (allowed_concurso_ids is None or concurso.id in allowed_concurso_ids):
            topics_in_concurso = concurso.laws.filter(Law.parent_id.isnot(None)).all()
            topic_ids_to_show = {topic.id for topic in topics_in_concurso}
            
            parent_ids = {topic.parent_id for topic in topics_in_concurso if topic.parent_id}
            
            diplomas_query = diplomas_query.filter(Law.id.in_(parent_ids))
    else:
        selected_subject_id = int(selected_subject_id_str) if selected_subject_id_str.isdigit() else None
        if selected_subject_id:
            diplomas_query = diplomas_query.filter(Law.subject_id == selected_subject_id)

    selected_diploma_id = int(selected_diploma_id_str) if selected_diploma_id_str.isdigit() else None
    if selected_diploma_id:
        diplomas_query = diplomas_query.filter(Law.id == selected_diploma_id)

    all_diplomas = diplomas_query.join(Law.subject).order_by(Subject.name, Law.title).all()
    
    selected_topic_id = int(selected_topic_id_str) if selected_topic_id_str.isdigit() else None
    
    processed_diplomas = []
    for diploma in all_diplomas:
        children_to_display = []
        
        children_iterator = diploma.children
        if topic_ids_to_show is not None:
            children_iterator = [child for child in diploma.children if child.id in topic_ids_to_show]
        elif allowed_law_ids is not None:
            children_iterator = [child for child in diploma.children if child.id in allowed_law_ids]

        for topic in children_iterator:
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
            allowed_children_ids_in_diploma = {child.id for child in children_iterator}
            total_children_in_diploma = len(allowed_children_ids_in_diploma)
            completed_children_count = sum(1 for child_id in allowed_children_ids_in_diploma if child_id in completed_topic_ids)
            progress_percentage = (completed_children_count / total_children_in_diploma * 100) if total_children_in_diploma > 0 else 0
            
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
    _, allowed_law_ids, _ = get_user_permissions()
    if allowed_law_ids is not None and law_id not in allowed_law_ids:
        flash("Você não tem permissão para acessar este tópico.", "danger")
        return redirect(url_for('student.dashboard'))
    
    law = Law.query.options(joinedload(Law.banner)).get_or_404(law_id)
    if law.parent_id is None:
        flash("Selecione um tópico de estudo específico para visualizar.", "info")
        return redirect(url_for('student.dashboard'))
    _record_study_activity(current_user)
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
    banner_to_show = None
    if law.banner:
        seen_banner_record = UserSeenLawBanner.query.filter_by(
            user_id=current_user.id,
            law_id=law_id,
            seen_at_timestamp=law.banner.last_updated
        ).first()
        if not seen_banner_record:
            banner_to_show = law.banner
    return render_template("student/view_law.html",
                           law=law, is_completed=(progress.status == 'concluido'),
                           last_read_article=progress.last_read_article, current_status=progress.status,
                           is_favorited=is_favorited, display_content=content_to_display,
                           banner_to_show=banner_to_show
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
        unlocked_achievements_obj = check_and_award_achievements(current_user)
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
            flash(f"Erro ao salvar progresso: {e}", "danger")
            logging.error(f"Erro ao salvar progresso para law_id {law_id}: {e}")
            return jsonify(success=False, error=str(e)), 500
    else:
        flash(f"Você já marcou \"{law.title}\" como concluída.", "info")
    return jsonify(
        success=True,
        unlocked_achievements=unlocked_achievements
    )

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
    last_read_article = bleach.clean(request.form.get("last_read_article", "").strip(), tags=[], strip=True)
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

@student_bp.route("/law/<int:law_id>/mark_banner_seen", methods=["POST"])
@login_required
def mark_banner_seen(law_id):
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

@student_bp.route("/law/<int:law_id>/notes", methods=["GET", "POST"])
@login_required
def handle_user_notes(law_id):
    if request.method == "GET":
        notes = UserNotes.query.filter_by(user_id=current_user.id, law_id=law_id).first()
        return jsonify(success=True, content=notes.content if notes else "")
    if request.method == "POST":
        untrusted_content = request.json.get("content") or ""
        sanitized_content = bleach.clean(untrusted_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer, strip=True)
        notes = UserNotes.query.filter_by(user_id=current_user.id, law_id=law_id).first()
        if notes:
            notes.content = sanitized_content
        else:
            notes = UserNotes(user_id=current_user.id, law_id=law_id, content=sanitized_content)
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
        
        untrusted_content = data.get('content') or ""
        
        sanitized_content = bleach.clean(untrusted_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer, strip=True)
        
        user_markup = UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).first()
        if user_markup:
            user_markup.content = sanitized_content
        else:
            new_markup = UserLawMarkup(user_id=current_user.id, law_id=law_id, content=sanitized_content)
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
        content = bleach.clean(data.get("content", ""), tags=[], strip=True)
        anchor_id = bleach.clean(data.get("anchor_paragraph_id", ""), tags=[], strip=True)
        
        if not content or not anchor_id:
            return jsonify(success=False, error="Conteúdo e âncora são obrigatórios."), 400

        new_comment = UserComment(
            content=content,
            anchor_paragraph_id=anchor_id,
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
        untrusted_content = request.json.get("content") or ""
        comment.content = bleach.clean(untrusted_content, tags=[], strip=True)
        db.session.commit()
        return jsonify(success=True, message="Anotação atualizada!", comment={"id": comment.id, "content": comment.content})
    if request.method == "DELETE":
        db.session.delete(comment)
        db.session.commit()
        return jsonify(success=True, message="Anotação excluída!")

@student_bp.route("/law/<int:law_id>/restore", methods=['POST'])
@login_required
def restore_law_to_original(law_id):
    Law.query.get_or_404(law_id)
    try:
        UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).delete()
        UserComment.query.filter_by(user_id=current_user.id, law_id=law_id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Lei restaurada com sucesso.'})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao restaurar a lei {law_id} para o usuário {current_user.id}: {e}")
        return jsonify({'success': False, 'error': 'Um erro interno ocorreu ao restaurar a lei.'}), 500

@student_bp.route("/api/save_favorite_title", methods=["POST"])
@login_required
def save_favorite_title():
    data = request.get_json()
    new_title = bleach.clean(data.get('title', ''), tags=[], strip=True).strip()
    if not new_title:
        return jsonify(success=False, error="O título não pode estar vazio."), 400
    if len(new_title) > 100:
        return jsonify(success=False, error="O título é muito longo."), 400
    try:
        current_user.favorite_label = new_title
        db.session.commit()
        return jsonify(success=True, message="Título salvo com sucesso!")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar título dos favoritos para o usuário {current_user.id}: {e}")
        return jsonify(success=False, error="Erro interno ao salvar o título."), 500

def _serialize_todo_item(item):
    """Função auxiliar para converter um objeto TodoItem em um dicionário JSON."""
    law_info = { "law_id": None, "law_title": None, "law_url": None }
    if item.law:
        law_info["law_id"] = item.law.id
        law_info["law_title"] = f"{item.law.parent.title} - {item.law.title}" if item.law.parent else item.law.title
        law_info["law_url"] = url_for('student.view_law', law_id=item.law.id)

    return {
        "id": item.id,
        "content": item.content,
        "is_completed": item.is_completed,
        "category": item.category,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        **law_info
    }

@student_bp.route("/api/todo_items", methods=["GET"])
@login_required
def get_todo_items():
    todo_items = current_user.todo_items.options(
        joinedload(TodoItem.law).joinedload(Law.parent)
    ).order_by(TodoItem.is_completed.asc(), TodoItem.created_at.desc()).all()
    
    items_data = [_serialize_todo_item(item) for item in todo_items]
    return jsonify(success=True, todo_items=items_data)

@student_bp.route("/api/todo_items", methods=["POST"])
@login_required
def add_todo_item():
    data = request.get_json()
    content = bleach.clean(data.get("content", ""), tags=[], strip=True).strip()
    category = data.get("category", "lembrete")
    law_id = data.get("law_id")

    if category not in ['lembrete', 'meta']:
        category = 'lembrete'

    if not content:
        return jsonify(success=False, error="O conteúdo não pode estar vazio."), 400

    if len(current_user.todo_items.all()) >= 10:
        return jsonify(success=False, error="Você atingiu o limite de 10 itens."), 400

    if law_id:
        try:
            law_id = int(law_id)
        except (ValueError, TypeError):
            return jsonify(success=False, error="ID de lei inválido."), 400

    new_item = TodoItem(
        user_id=current_user.id, 
        content=content, 
        category=category, 
        law_id=law_id,
        is_completed=False
    )
    try:
        db.session.add(new_item)
        db.session.commit()
        db.session.refresh(new_item)
        return jsonify(
            success=True,
            message="Item adicionado!",
            todo_item=_serialize_todo_item(new_item)
        ), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao adicionar item de lembrete/meta para o usuário {current_user.id}: {e}")
        return jsonify(success=False, error="Erro interno ao adicionar item."), 500

@student_bp.route("/api/todo_items/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_todo_item(item_id):
    item = TodoItem.query.options(
        joinedload(TodoItem.law).joinedload(Law.parent)
    ).filter_by(id=item_id, user_id=current_user.id).first()

    if not item:
        return jsonify(success=False, error="Item não encontrado."), 404
    
    item.is_completed = not item.is_completed
    item.completed_at = datetime.datetime.utcnow() if item.is_completed else None
    try:
        db.session.commit()
        message = "Item marcado como concluído!" if item.is_completed else "Item reaberto!"
        return jsonify(
            success=True,
            message=message,
            todo_item=_serialize_todo_item(item)
        )
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao alternar status do item {item_id} para o usuário {current_user.id}: {e}")
        return jsonify(success=False, error="Erro interno ao atualizar item."), 500

@student_bp.route("/api/todo_items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_todo_item(item_id):
    item = TodoItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify(success=False, error="Tarefa não encontrada."), 404
    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify(success=True, message="Tarefa excluída!")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir item de diário {item_id} para o usuário {current_user.id}: {e}")
        return jsonify(success=False, error="Erro interno ao excluir tarefa."), 500

@student_bp.route("/api/set_default_concurso", methods=["POST"])
@login_required
def set_default_concurso():
    data = request.get_json()
    concurso_id_str = data.get('concurso_id')

    try:
        if concurso_id_str == 'clear':
            current_user.default_concurso_id = None
            message = "Filtro padrão removido com sucesso!"
        elif concurso_id_str and concurso_id_str.isdigit():
            concurso_id = int(concurso_id_str)
            concurso = Concurso.query.get(concurso_id)
            if not concurso:
                return jsonify(success=False, error="Concurso não encontrado."), 404
            current_user.default_concurso_id = concurso_id
            message = "Concurso definido como padrão!"
        else:
            return jsonify(success=False, error="ID de concurso inválido."), 400

        db.session.commit()
        return jsonify(success=True, message=message)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao definir concurso padrão para o usuário {current_user.id}: {e}")
        return jsonify(success=False, error="Erro interno ao salvar a preferência."), 500


@student_bp.route("/api/study_sessions/record", methods=["POST"])
@login_required
def record_study_session():
    data = request.get_json()
    
    law_id = data.get('law_id')
    duration_seconds = data.get('duration_seconds')
    entry_type = data.get('entry_type', 'auto')

    if not law_id or duration_seconds is None:
        return jsonify(success=False, error="law_id e duration_seconds são obrigatórios."), 400
    
    try:
        law_id = int(law_id)
        duration_seconds = int(duration_seconds)
    except ValueError:
        return jsonify(success=False, error="law_id e duration_seconds devem ser números inteiros."), 400
    
    if duration_seconds <= 0:
        return jsonify(success=False, error="A duração da sessão deve ser maior que zero."), 400

    law = Law.query.get(law_id)
    if not law:
        return jsonify(success=False, error="Lei não encontrada."), 404

    subject_id = law.subject_id
    if not subject_id:
        return jsonify(success=False, error="A lei não está associada a uma matéria válida. Não é possível registrar o tempo de estudo."), 400
    
    start_time = None
    end_time = None
    if entry_type == 'auto':
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        try:
            start_time = datetime.datetime.fromisoformat(start_time_str.replace('Z', '+00:00')) if start_time_str else None
            end_time = datetime.datetime.fromisoformat(end_time_str.replace('Z', '+00:00')) if end_time_str else None
        except ValueError:
            return jsonify(success=False, error="Formato de data/hora inválido para start_time ou end_time."), 400
        
        if not start_time or not end_time:
            return jsonify(success=False, error="start_time e end_time são obrigatórios para sessões automáticas."), 400
        
        calculated_duration = (end_time - start_time).total_seconds()
        if abs(calculated_duration - duration_seconds) > 5:
            logging.warning(f"Duração calculada ({calculated_duration}) difere da enviada ({duration_seconds}) para user {current_user.id}, law {law_id}.")
            duration_seconds = int(calculated_duration)

    try:
        new_session = StudySession(
            user_id=current_user.id,
            law_id=law_id,
            subject_id=subject_id,
            duration_seconds=duration_seconds,
            entry_type=entry_type,
            start_time=start_time,
            end_time=end_time,
            recorded_at=datetime.datetime.utcnow()
        )
        db.session.add(new_session)
        
        _record_study_activity(current_user)

        db.session.commit()
        return jsonify(success=True, message="Sessão de estudo registrada com sucesso!")

    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao registrar sessão de estudo para user {current_user.id}, law {law_id}: {e}")
        return jsonify(success=False, error="Erro interno ao registrar sessão de estudo."), 500

@student_bp.route("/api/study_stats", methods=["GET"])
@login_required
def get_study_stats():
    study_data = db.session.query(
        Subject.name,
        func.sum(StudySession.duration_seconds).label('total_duration_seconds')
    ).join(Subject, StudySession.subject_id == Subject.id)\
     .filter(StudySession.user_id == current_user.id)\
     .group_by(Subject.name)\
     .order_by(Subject.name)\
     .all()
    
    stats_by_subject = []
    total_study_seconds = 0
    for subject_name, duration_seconds in study_data:
        total_study_seconds += duration_seconds
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        stats_by_subject.append({
            'subject_name': subject_name,
            'total_seconds': duration_seconds,
            'formatted_duration': f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        })
    
    total_hours = total_study_seconds // 3600
    total_minutes = (total_study_seconds % 3600) // 60

    return jsonify(success=True, 
                   stats_by_subject=stats_by_subject,
                   total_study_seconds=total_study_seconds,
                   total_formatted_duration=f"{int(total_hours)}h {int(total_minutes)}m"
                )

# =====================================================================
# <<< INÍCIO DA ALTERAÇÃO FINAL: ROTAS DE COMUNIDADE >>>
# =====================================================================
@student_bp.route("/law/<int:law_id>/share_contribution", methods=["POST"])
@login_required
def share_contribution(law_id):
    existing_contribution = CommunityContribution.query.filter_by(
        user_id=current_user.id,
        law_id=law_id,
        status='pending'
    ).first()
    if existing_contribution:
        return jsonify(success=False, error="Você já enviou suas marcações para análise. Por favor, aguarde a revisão."), 400

    user_markup = UserLawMarkup.query.filter_by(user_id=current_user.id, law_id=law_id).first()
    user_comments = UserComment.query.filter_by(user_id=current_user.id, law_id=law_id).all()

    base_content = user_markup.content if user_markup else Law.query.get(law_id).content
    if not base_content and not user_comments:
         return jsonify(success=False, error="Não há conteúdo para compartilhar."), 400

    try:
        new_contribution = CommunityContribution(
            user_id=current_user.id,
            law_id=law_id,
            content=base_content or "",
            status='pending'
        )
        db.session.add(new_contribution)
        db.session.flush()

        for comment in user_comments:
            new_community_comment = CommunityComment(
                contribution_id=new_contribution.id,
                content=comment.content,
                anchor_paragraph_id=comment.anchor_paragraph_id
            )
            db.session.add(new_community_comment)
        
        db.session.commit()
        return jsonify(success=True, message="Sua contribuição completa foi enviada para análise. Muito obrigado!")
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar contribuição do usuário {current_user.id} para a lei {law_id}: {e}")
        return jsonify(success=False, error="Ocorreu um erro interno ao enviar sua contribuição."), 500

@student_bp.route("/api/law/<int:law_id>/community-version")
@login_required
def get_community_version(law_id):
    law = Law.query.get_or_404(law_id)
    if not law.approved_contribution_id:
        return jsonify(success=False, error="Nenhuma versão da comunidade foi aprovada para esta lei ainda."), 404

    approved_contribution = law.approved_contribution
    if not approved_contribution:
        return jsonify(success=False, error="A versão da comunidade não pôde ser encontrada."), 404

    comments_data = [
        {
            "content": comment.content,
            "anchor_paragraph_id": comment.anchor_paragraph_id
        } 
        for comment in approved_contribution.comments
    ]

    return jsonify(
        success=True, 
        content=approved_contribution.content,
        comments=comments_data
    )
# =====================================================================
# <<< FIM DA ALTERAÇÃO FINAL >>>
# =====================================================================
