# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy.orm import joinedload
import datetime
# NOVO: Importar a biblioteca de sanitização
import bleach
from src.models.user import db, User, Announcement, UserSeenAnnouncement, LawBanner
from src.models.law import Law, Subject, UsefulLink 
from src.models.progress import UserProgress 

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# NOVO: Definição central de tags e atributos HTML que são permitidos
# nos campos de texto rico (como o corpo da lei ou dos anúncios).
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 
    'ul', 'ol', 'li', 'a', 'blockquote',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'span', 'div', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]
ALLOWED_ATTRIBUTES = {
    '*': ['style', 'class'], # Permite style e class em qualquer tag
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'height', 'width']
}


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Acesso não autorizado.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
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

    pending_users_count = User.query.filter_by(is_approved=False, role="student").count()
    active_announcements_count = Announcement.query.filter_by(is_active=True).count()
    
    return render_template("admin/dashboard.html", 
                           subjects_with_diplomas=subjects_with_diplomas,
                           pending_users_count=pending_users_count,
                           active_announcements_count=active_announcements_count,
                           all_subjects=all_subjects,
                           selected_subject=subject_filter)

@admin_bp.route("/subjects", methods=["GET", "POST"])
@login_required
@admin_required
def manage_subjects():
    if request.method == "POST":
        # ALTERADO: Sanitiza o nome da matéria para remover qualquer tag HTML
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


@admin_bp.route("/laws/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_law():
    pre_selected_parent_id = request.args.get('parent_id', type=int)
    
    subjects = Subject.query.order_by(Subject.name).all()
    normative_acts = Law.query.filter(Law.parent_id.is_(None)).order_by(Law.title).all()

    if request.method == "POST":
        # ALTERADO: Sanitiza todos os campos de texto recebidos do formulário
        title = bleach.clean(request.form.get("title", ""), tags=[], strip=True)
        description = bleach.clean(request.form.get("description", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        content = bleach.clean(request.form.get("content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        subject_id = request.form.get("subject_id")
        parent_id = request.form.get("parent_id")
        audio_url = bleach.clean(request.form.get("audio_url", ""), tags=[], strip=True)
        juridiques_explanation = bleach.clean(request.form.get("juridiques_explanation", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        banner_content = bleach.clean(request.form.get("banner_content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES).strip()

        if not title:
            flash("O Título é obrigatório.", "danger")
            return render_template("admin/add_edit_law.html", law=None, subjects=subjects, normative_acts=normative_acts, pre_selected_parent_id=pre_selected_parent_id)

        new_law = Law(
            title=title, 
            description=description, 
            content=content,
            audio_url=audio_url if audio_url else None,
            juridiques_explanation=juridiques_explanation if juridiques_explanation else None
        )
        
        new_law.subject_id = int(subject_id) if subject_id and subject_id != "None" else None
        new_law.parent_id = int(parent_id) if parent_id and parent_id != "" else None
            
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
            # ALTERADO: Sanitiza os títulos e URLs dos links
            link_title = bleach.clean(request.form.get(f'link-{index}-title', ""), tags=[], strip=True)
            link_url = bleach.clean(request.form.get(f'link-{index}-url', ""), tags=[], strip=True)
            if link_title and link_url:
                new_link = UsefulLink(title=link_title, url=link_url, law_id=new_law.id)
                db.session.add(new_link)
            index += 1
        
        db.session.commit()
        flash("Item de estudo adicionado com sucesso!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/add_edit_law.html", 
                           law=None, 
                           subjects=subjects, 
                           normative_acts=normative_acts,
                           pre_selected_parent_id=pre_selected_parent_id)


@admin_bp.route("/laws/edit/<int:law_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_law(law_id):
    law = Law.query.options(joinedload(Law.banner)).get_or_404(law_id)
    subjects = Subject.query.order_by(Subject.name).all()
    normative_acts = Law.query.filter(Law.parent_id.is_(None), Law.id != law_id).order_by(Law.title).all()

    if request.method == "POST":
        # ALTERADO: Sanitiza todos os campos de texto antes de atualizar o objeto
        law.title = bleach.clean(request.form.get("title"), tags=[], strip=True)
        law.description = bleach.clean(request.form.get("description"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        law.content = bleach.clean(request.form.get("content"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        law.juridiques_explanation = bleach.clean(request.form.get("juridiques_explanation"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        banner_content = bleach.clean(request.form.get("banner_content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES).strip()
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
            return render_template("admin/add_edit_law.html", law=law, subjects=subjects, normative_acts=normative_acts)

        law.subject_id = int(subject_id) if subject_id and subject_id != "None" else None
        law.parent_id = int(parent_id) if parent_id and parent_id != "" else None
        law.audio_url = audio_url if audio_url else None

        UsefulLink.query.filter_by(law_id=law.id).delete()
        index = 0
        while f'link-{index}-title' in request.form:
            # ALTERADO: Sanitiza os títulos e URLs dos links
            link_title = bleach.clean(request.form.get(f'link-{index}-title'), tags=[], strip=True)
            link_url = bleach.clean(request.form.get(f'link-{index}-url'), tags=[], strip=True)
            if link_title and link_url:
                new_link = UsefulLink(title=link_title, url=link_url, law_id=law.id)
                db.session.add(new_link)
            index += 1

        db.session.commit()
        flash("Item de estudo atualizado com sucesso!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/add_edit_law.html", law=law, subjects=subjects, normative_acts=normative_acts)

@admin_bp.route("/laws/delete/<int:law_id>", methods=["POST"])
@login_required
@admin_required
def delete_law(law_id):
    law = Law.query.get_or_404(law_id)
    try:
        db.session.delete(law)
        db.session.commit()
        flash("Item e todos os seus dados relacionados foram excluídos!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir o item: {e}", "danger")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/users")
@login_required
@admin_required
def manage_users():
    users = User.query.filter(User.role != "admin").order_by(User.is_approved.asc(), User.email.asc()).all()
    return render_template("admin/manage_users.html", users=users)

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
    else:
        email = user.email
        db.session.delete(user)
        db.session.commit()
        flash(f"Usuário {email} e seus dados foram excluídos com sucesso!", "warning")
    return redirect(url_for("admin.manage_users"))

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

@admin_bp.route("/announcements", methods=["GET", "POST"])
@login_required
@admin_required
def manage_announcements():
    if request.method == "POST":
        # ALTERADO: Sanitiza os campos do anúncio
        title = bleach.clean(request.form.get("title"), tags=[], strip=True)
        content = bleach.clean(request.form.get("content"), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
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
        UserSeenAnnouncement.query.filter_by(announcement_id=announcement_id).delete()
        db.session.delete(announcement)
        db.session.commit()
        flash("Aviso excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir o aviso: {e}", "danger")
    return redirect(url_for('admin.manage_announcements'))
