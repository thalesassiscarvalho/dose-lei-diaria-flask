# src/routes/admin.py

# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
import datetime
import bleach
from bleach.css_sanitizer import CSSSanitizer

# Importações completas e corretas
from src.extensions import db
from src.models.user import User, Announcement, UserSeenAnnouncement, LawBanner, UserSeenLawBanner, StudyActivity, TodoItem, CommunityContribution
from src.models.law import Law, Subject, UsefulLink
from src.models.progress import UserProgress
from src.models.comment import UserComment
from src.models.notes import UserNotes, UserLawMarkup
from src.models.concurso import Concurso
from src.models.study import StudySession


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 
    'ul', 'ol', 'li', 'a', 'blockquote',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'span', 'div', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]
ALLOWED_ATTRIBUTES = {
    '*': ['style', 'class'],
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'height', 'width']
}
ALLOWED_STYLES = [
    'color', 'background-color', 'font-weight', 'font-style', 'text-decoration',
    'text-align', 'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'border', 'border-left'
]
css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Acesso não autorizado.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

# Rota do dashboard
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = {
        'total_users': User.query.filter_by(role="student").count(),
        'active_users_week': UserProgress.query.filter(UserProgress.last_accessed_at >= (datetime.datetime.utcnow() - datetime.timedelta(days=7))).distinct(UserProgress.user_id).count(),
        'total_laws': Law.query.filter(Law.parent_id.isnot(None)).count(),
    }
    pending_users_count = User.query.filter_by(is_approved=False, role="student").count()
    active_announcements_count = Announcement.query.filter_by(is_active=True).count()
    
    pending_contributions_count = CommunityContribution.query.filter_by(status='pending').count()

    charts_data = {
        'new_users': {'labels': [], 'values': []},
        'top_content': {'labels': [], 'values': []}
    }

    return render_template("admin/dashboard.html",
                           stats=stats,
                           pending_users_count=pending_users_count,
                           charts_data=charts_data,
                           active_announcements_count=active_announcements_count,
                           pending_contributions_count=pending_contributions_count 
                           )

# Rota de gerenciamento de conteúdo
@admin_bp.route('/content-management')
@login_required
@admin_required
def content_management():
    subject_filter = request.args.get("subject_filter", "all")
    all_subjects = Subject.query.order_by(Subject.name).all()
    
    query = Law.query.outerjoin(Subject).filter(Law.parent_id.is_(None)).options(
        joinedload(Law.children)
    ).order_by(Subject.name, Law.title)

    if subject_filter and subject_filter != "all":
        try:
            subject_id = int(subject_filter)
            query = query.filter(Law.subject_id == subject_id)
        except ValueError:
            if subject_filter == "none":
                query = query.filter(Law.subject_id.is_(None))

    diplomas = query.all()
    
    subjects_with_diplomas = {}
    for diploma in diplomas:
        subject_name = diploma.subject.name if diploma.subject else "Sem Matéria"
        if subject_name not in subjects_with_diplomas:
            subjects_with_diplomas[subject_name] = []
        subjects_with_diplomas[subject_name].append(diploma)

    return render_template("admin/content_management.html", 
                           subjects_with_diplomas=subjects_with_diplomas,
                           all_subjects=all_subjects,
                           selected_subject=subject_filter)


# Rotas para Gerenciar Concursos
@admin_bp.route("/concursos", methods=["GET", "POST"])
@login_required
@admin_required
def manage_concursos():
    if request.method == "POST":
        concurso_name = bleach.clean(request.form.get("name"), tags=[], strip=True).strip()
        if concurso_name:
            existing_concurso = Concurso.query.filter_by(name=concurso_name).first()
            if not existing_concurso:
                new_concurso = Concurso(name=concurso_name)
                db.session.add(new_concurso)
                db.session.commit()
                flash(f"Concurso '{concurso_name}' adicionado com sucesso!", "success")
            else:
                flash(f"Concurso '{concurso_name}' já existe.", "warning")
        else:
            flash("Nome do concurso não pode ser vazio.", "danger")
        return redirect(url_for("admin.manage_concursos"))
    
    concursos = Concurso.query.order_by(Concurso.name).all()
    return render_template("admin/manage_concursos.html", concursos=concursos)


@admin_bp.route("/concursos/edit/<int:concurso_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_concurso(concurso_id):
    concurso = Concurso.query.get_or_404(concurso_id)
    if request.method == "POST":
        name = bleach.clean(request.form.get("name"), tags=[], strip=True).strip()
        edital_url = bleach.clean(request.form.get("edital_url"), tags=[], strip=True).strip()
        
        if not name:
            flash("O nome do concurso não pode ser vazio.", "danger")
        else:
            concurso.name = name
            concurso.edital_verticalizado_url = edital_url if edital_url else None
            db.session.commit()
            flash(f"Concurso '{concurso.name}' atualizado com sucesso!", "success")
            return redirect(url_for("admin.manage_concursos"))
            
    return render_template("admin/edit_concurso.html", concurso=concurso)


@admin_bp.route("/concursos/delete/<int:concurso_id>", methods=["POST"])
@login_required
@admin_required
def delete_concurso(concurso_id):
    concurso = Concurso.query.get_or_404(concurso_id)
    try:
        db.session.delete(concurso)
        db.session.commit()
        flash(f"Concurso '{concurso.name}' excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir concurso {concurso_id}: {e}")
        flash("Erro ao excluir o concurso.", "danger")
    return redirect(url_for("admin.manage_concursos"))


# Rota para gerenciar matérias
@admin_bp.route("/subjects", methods=["GET", "POST"])
@login_required
@admin_required
def manage_subjects():
    if request.method == "POST":
        subject_name = bleach.clean(request.form.get("name"), tags=[], strip=True).strip()
        if subject_name:
            existing_subject = Subject.query.filter_by(name=subject_name).first()
            if not existing_subject:
                new_subject = Subject(name=subject_name)
                db.session.add(new_subject)
                db.session.commit()
                flash(f"Matéria '{subject_name}' adicionada com sucesso!", "success")
            else:
                flash(f"Matéria '{subject_name}' já existe.", "warning")
        else:
            flash("Nome da matéria não pode ser vazio.", "danger")
        return redirect(url_for("admin.manage_subjects"))
    subjects = Subject.query.order_by(Subject.name).all()
    return render_template("admin/manage_subjects.html", subjects=subjects)

# Rota para deletar matérias
@admin_bp.route("/subjects/delete/<int:subject_id>", methods=["POST"])
@login_required
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.laws:
        flash(f"Não é possível excluir a matéria '{subject.name}', pois ela contém itens de estudo associados.", "danger")
    else:
        db.session.delete(subject)
        db.session.commit()
        flash(f"Matéria '{subject.name}' excluída com sucesso!", "success")
    return redirect(url_for("admin.manage_subjects"))


# Rota para adicionar lei
@admin_bp.route("/laws/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_law():
    pre_selected_parent_id = request.args.get('parent_id', type=int)
    
    subjects = Subject.query.order_by(Subject.name).all()
    normative_acts = Law.query.filter(Law.parent_id.is_(None)).order_by(Law.title).all()
    concursos = Concurso.query.order_by(Concurso.name).all()

    if request.method == "POST":
        title = bleach.clean(request.form.get("title", ""), tags=[], strip=True)
        description = bleach.clean(request.form.get("description", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        content = bleach.clean(request.form.get("content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        juridiques_explanation = bleach.clean(request.form.get("juridiques_explanation", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        banner_content = bleach.clean(request.form.get("banner_content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer).strip()
        
        subject_id = request.form.get("subject_id")
        parent_id = request.form.get("parent_id")
        audio_url = bleach.clean(request.form.get("audio_url", ""), tags=[], strip=True)

        if not title:
            flash("O Título é obrigatório.", "danger")
            return render_template("admin/add_edit_law.html", law=None, subjects=subjects, normative_acts=normative_acts, pre_selected_parent_id=pre_selected_parent_id, concursos=concursos)

        new_law = Law(
            title=title, 
            description=description, 
            content=content,
            audio_url=audio_url if audio_url else None,
            juridiques_explanation=juridiques_explanation if juridiques_explanation else None
        )
        
        new_law.subject_id = int(subject_id) if subject_id and subject_id != "None" else None
        new_law.parent_id = int(parent_id) if parent_id and parent_id != "" else None
        
        concurso_ids = request.form.getlist('concursos')
        if concurso_ids:
            selected_concursos = Concurso.query.filter(Concurso.id.in_(concurso_ids)).all()
            new_law.concursos = selected_concursos
            
        db.session.add(new_law)
        db.session.flush()

        if banner_content:
            new_banner = LawBanner(
                content=banner_content,
                law_id=new_law.id
            )
            db.session.add(new_banner)

        index = 0
        while f'link-{index}-title' in request.form:
            link_title = bleach.clean(request.form.get(f'link-{index}-title', ""), tags=[], strip=True)
            link_url = bleach.clean(request.form.get(f'link-{index}-url', ""), tags=[], strip=True)
            if link_title and link_url:
                new_link = UsefulLink(title=link_title, url=link_url, law_id=new_law.id)
                db.session.add(new_link)
            index += 1
        
        db.session.commit()
        flash("Item de estudo adicionado com sucesso!", "success")
        return redirect(url_for("admin.content_management"))

    return render_template("admin/add_edit_law.html", 
                           law=None, 
                           subjects=subjects, 
                           normative_acts=normative_acts,
                           pre_selected_parent_id=pre_selected_parent_id,
                           concursos=concursos)

# Rota para editar lei
@admin_bp.route("/laws/edit/<int:law_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_law(law_id):
    law = Law.query.options(joinedload(Law.banner), joinedload(Law.concursos)).get_or_404(law_id)
    subjects = Subject.query.order_by(Subject.name).all()
    normative_acts = Law.query.filter(Law.parent_id.is_(None), Law.id != law_id).order_by(Law.title).all()
    concursos = Concurso.query.order_by(Concurso.name).all()

    if request.method == "POST":
        law.title = bleach.clean(request.form.get("title"), tags=[], strip=True)
        law.description = bleach.clean(request.form.get("description"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        law.content = bleach.clean(request.form.get("content"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        law.juridiques_explanation = bleach.clean(request.form.get("juridiques_explanation"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        banner_content = bleach.clean(request.form.get("banner_content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer).strip()
        
        audio_url = bleach.clean(request.form.get("audio_url", ""), tags=[], strip=True)
        subject_id = request.form.get("subject_id")
        parent_id = request.form.get("parent_id")
        
        law_banner = law.banner

        if banner_content:
            if law_banner:
                if law_banner.content != banner_content:
                    law_banner.content = banner_content
                    law_banner.last_updated = datetime.datetime.utcnow()
            else:
                new_banner = LawBanner(content=banner_content, law_id=law.id)
                db.session.add(new_banner)
        elif law_banner:
            db.session.delete(law_banner)

        if not law.title:
            flash("O Título é obrigatório.", "danger")
            return render_template("admin/add_edit_law.html", law=law, subjects=subjects, normative_acts=normative_acts, concursos=concursos)

        law.subject_id = int(subject_id) if subject_id and subject_id != "None" else None
        law.parent_id = int(parent_id) if parent_id and parent_id != "" else None
        law.audio_url = audio_url if audio_url else None
        
        concurso_ids = request.form.getlist('concursos')
        selected_concursos = Concurso.query.filter(Concurso.id.in_(concurso_ids)).all()
        law.concursos = selected_concursos

        UsefulLink.query.filter_by(law_id=law.id).delete()
        index = 0
        while f'link-{index}-title' in request.form:
            link_title = bleach.clean(request.form.get(f'link-{index}-title'), tags=[], strip=True)
            link_url = bleach.clean(request.form.get(f'link-{index}-url'), tags=[], strip=True)
            if link_title and link_url:
                new_link = UsefulLink(title=link_title, url=link_url, law_id=law.id)
                db.session.add(new_link)
            index += 1

        db.session.commit()
        flash("Item de estudo atualizado com sucesso!", "success")
        return redirect(url_for("admin.content_management"))

    return render_template("admin/add_edit_law.html", law=law, subjects=subjects, normative_acts=normative_acts, concursos=concursos)

# Rota para deletar leis
@admin_bp.route("/laws/delete/<int:law_id>", methods=["POST"])
@login_required
@admin_required
def delete_law(law_id):
    law = Law.query.options(joinedload(Law.children)).get_or_404(law_id)
    try:
        ids_to_delete = [law.id]
        def collect_child_ids(current_law):
            for child in current_law.children:
                ids_to_delete.append(child.id)
                collect_child_ids(child)
        collect_child_ids(law)
        
        UserComment.query.filter(UserComment.law_id.in_(ids_to_delete)).delete(synchronize_session=False)
        UserNotes.query.filter(UserNotes.law_id.in_(ids_to_delete)).delete(synchronize_session=False)
        UserLawMarkup.query.filter(UserLawMarkup.law_id.in_(ids_to_delete)).delete(synchronize_session=False)
        UserSeenLawBanner.query.filter(UserSeenLawBanner.law_id.in_(ids_to_delete)).delete(synchronize_session=False)
        LawBanner.query.filter(LawBanner.law_id.in_(ids_to_delete)).delete(synchronize_session=False)
        UsefulLink.query.filter(UsefulLink.law_id.in_(ids_to_delete)).delete(synchronize_session=False)
        UserProgress.query.filter(UserProgress.law_id.in_(ids_to_delete)).delete(synchronize_session=False)

        db.session.delete(law)
        db.session.commit()
        flash("Item e todos os seus dados relacionados foram excluídos!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Falha ao excluir a lei ID {law_id}. Erro: {e}", exc_info=True)
        flash(f"Erro ao excluir o item. Verifique o log da aplicação para mais detalhes.", "danger")
    return redirect(url_for("admin.content_management"))

@admin_bp.route("/users")
@login_required
@admin_required
def manage_users():
    search_query = request.args.get('search', '').strip()
    
    query = User.query.filter(User.role != "admin")

    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )

    users = query.order_by(User.is_approved.asc(), User.created_at.desc()).all()
    
    return render_template("admin/manage_users.html", users=users, search_query=search_query)


@admin_bp.route("/users/approve/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"Usuário {user.email} aprovado com sucesso!", "success")
    return redirect(url_for("admin.manage_users"))

@admin_bp.route("/users/deny/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def deny_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        flash("Não é possível excluir um administrador.", "danger")
        return redirect(url_for("admin.manage_users"))

    try:
        email = user.email
        
        UserComment.query.filter_by(user_id=user_id).delete()
        UserProgress.query.filter_by(user_id=user_id).delete()
        UserSeenAnnouncement.query.filter_by(user_id=user_id).delete()
        UserSeenLawBanner.query.filter_by(user_id=user_id).delete()
        StudyActivity.query.filter_by(user_id=user_id).delete()
        TodoItem.query.filter_by(user_id=user_id).delete()
        UserNotes.query.filter_by(user_id=user_id).delete()
        UserLawMarkup.query.filter_by(user_id=user_id).delete()
        StudySession.query.filter_by(user_id=user_id).delete()
        
        user.achievements = []
        user.favorite_laws = []
        
        db.session.delete(user)
        db.session.commit()
        flash(f"Usuário {email} e seus dados foram excluídos com sucesso!", "warning")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Falha ao negar o usuário ID {user_id}. Erro: {e}", exc_info=True)
        flash(f"Ocorreu um erro ao excluir o usuário. Verifique o log da aplicação.", "danger")

    return redirect(url_for("admin.manage_users"))

@admin_bp.route("/users/<int:user_id>/manage-concursos", methods=["GET", "POST"])
@login_required
@admin_required
def manage_user_concursos(user_id):
    user = User.query.get_or_404(user_id)
    all_concursos = Concurso.query.order_by(Concurso.name).all()

    if request.method == "POST":
        can_see_all = request.form.get("can_see_all_concursos") == "on"
        user.can_see_all_concursos = can_see_all

        if can_see_all:
            user.associated_concursos = []
        else:
            concurso_ids = request.form.getlist('concursos')
            selected_concursos = Concurso.query.filter(Concurso.id.in_(concurso_ids)).all()
            user.associated_concursos = selected_concursos

        db.session.commit()
        flash(f"As permissões de concurso para {user.email} foram atualizadas com sucesso!", "success")
        return redirect(url_for("admin.manage_users"))

    user_concurso_ids = {c.id for c in user.associated_concursos}

    return render_template(
        "admin/manage_user_concursos.html",
        user=user,
        all_concursos=all_concursos,
        user_concurso_ids=user_concurso_ids
    )

@admin_bp.route("/users/reset-password/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        new_password = request.form.get("new_password")
        if not new_password:
            flash("A nova senha não pode estar vazia.", "danger")
        else:
            user.set_password(new_password)
            db.session.commit()
            flash(f"Senha do usuário {user.email} redefinida com sucesso!", "success")
        return redirect(url_for("admin.manage_users"))
    return render_template("admin/reset_password.html", user=user)


# Rotas de gerenciamento de anúncios
@admin_bp.route("/announcements", methods=["GET", "POST"])
@login_required
@admin_required
def manage_announcements():
    if request.method == "POST":
        title = bleach.clean(request.form.get("title"), tags=[], strip=True)
        content = bleach.clean(request.form.get("content"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        is_active = request.form.get("is_active") == "on"
        is_fixed = request.form.get("is_fixed") == "on"
        announcement_id = request.form.get("announcement_id")

        if not title or not content:
            flash("Título e conteúdo são obrigatórios.", "danger")
        else:
            try:
                if announcement_id:
                    announcement = Announcement.query.get_or_404(int(announcement_id))
                    announcement.title = title
                    announcement.content = content
                    announcement.is_active = is_active
                    announcement.is_fixed = is_fixed
                    flash("Aviso atualizado com sucesso!", "success")
                else:
                    new_announcement = Announcement(title=title, content=content, is_active=is_active, is_fixed=is_fixed)
                    db.session.add(new_announcement)
                    flash("Aviso adicionado com sucesso!", "success")
                
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao salvar o aviso: {e}", "danger")
        
        return redirect(url_for("admin.manage_announcements"))
        
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("admin/manage_announcements.html", announcements=announcements)

@admin_bp.route("/announcements/toggle/<int:announcement_id>", methods=["POST"])
@login_required
@admin_required
def toggle_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    announcement.is_active = not announcement.is_active
    db.session.commit()
    status = "ativado" if announcement.is_active else "desativado"
    flash(f"Aviso '{announcement.title}' foi {status}.", "success")
    return redirect(url_for('admin.manage_announcements'))

@admin_bp.route("/announcements/delete/<int:announcement_id>", methods=["POST"])
@login_required
@admin_required
def delete_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    try:
        db.session.delete(announcement)
        db.session.commit()
        flash("Aviso excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Falha ao excluir o aviso ID {announcement_id}. Erro: {e}", exc_info=True)
        flash(f"Erro ao excluir o aviso: {e}", "danger")
    return redirect(url_for('admin.manage_announcements'))

@admin_bp.route("/users/details/<int:user_id>")
@login_required
@admin_required
def user_details(user_id):
    user = User.query.get_or_404(user_id)

    total_seconds = db.session.query(db.func.sum(StudySession.duration_seconds)).filter_by(user_id=user_id).scalar() or 0
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    study_time_formatted = f"{int(hours)}h {int(minutes)}min"

    progress_items = UserProgress.query.filter_by(user_id=user_id).options(
        joinedload(UserProgress.law)
    ).order_by(UserProgress.last_accessed_at.desc()).all()

    favorite_items = user.favorite_laws.all()

    stats = {
        'study_time': study_time_formatted,
        'progress_count': len(progress_items),
        'favorites_count': len(favorite_items)
    }

    return render_template(
        "admin/user_details.html", 
        user=user, 
        stats=stats,
        progress_items=progress_items,
        favorite_items=favorite_items
    )

# =====================================================================
# <<< INÍCIO DA ALTERAÇÃO FINAL: ROTAS DE REVISÃO SEM DUPLICATAS >>>
# =====================================================================
@admin_bp.route("/community-contributions")
@login_required
@admin_required
def review_contributions():
    pending_contributions = CommunityContribution.query.options(
        joinedload(CommunityContribution.user),
        joinedload(CommunityContribution.law).joinedload(Law.parent)
    ).filter_by(status='pending').order_by(CommunityContribution.created_at.asc()).all()
    
    return render_template("admin/review_contributions.html", contributions=pending_contributions)

@admin_bp.route("/community-contributions/review/<int:contribution_id>")
@login_required
@admin_required
def review_contribution_detail(contribution_id):
    contribution = CommunityContribution.query.options(
        joinedload(CommunityContribution.user),
        joinedload(CommunityContribution.law).joinedload(Law.parent)
    ).get_or_404(contribution_id)
    
    return render_template("admin/review_contribution_detail.html", contribution=contribution)

@admin_bp.route("/community-contributions/process/<int:contribution_id>", methods=["POST"])
@login_required
@admin_required
def process_contribution(contribution_id):
    contribution = CommunityContribution.query.get_or_404(contribution_id)
    
    action = request.form.get("action")
    notes = request.form.get("reviewer_notes", "").strip()

    if action == "approve":
        contribution.status = "approved"
        contribution.law.approved_contribution_id = contribution.id
        contribution.reviewer_notes = notes
        contribution.reviewed_at = datetime.datetime.utcnow()
        flash("Contribuição APROVADA e definida como a nova versão da comunidade!", "success")

    elif action == "reject":
        contribution.status = "rejected"
        contribution.reviewer_notes = notes
        contribution.reviewed_at = datetime.datetime.utcnow()
        flash("Contribuição rejeitada com sucesso.", "info")
        
    else:
        flash("Ação inválida.", "danger")
        return redirect(url_for('admin.review_contribution_detail', contribution_id=contribution.id))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Ocorreu um erro ao processar a contribuição: {e}", "danger")
        current_app.logger.error(f"Erro ao processar contribuição {contribution_id}: {e}")
        
    return redirect(url_for('admin.review_contributions'))

# =====================================================================
# <<< FIM DA ALTERAÇÃO FINAL >>>
# =====================================================================
