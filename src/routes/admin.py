# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy.orm import joinedload
from src.models.user import db, User, Announcement, UserSeenAnnouncement 
from src.models.law import Law, Subject, UsefulLink 
from src.models.progress import UserProgress 

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Decorator (sem alterações)
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
    
    # =====================================================================
    # <<< INÍCIO DA CORREÇÃO >>>
    # A query foi reescrita para fazer um `outerjoin` explícito com a tabela
    # `Subject` antes de tentar ordenar por `Subject.name`.
    # =====================================================================
    query = Law.query.outerjoin(Subject).filter(Law.parent_id.is_(None)).options(
        joinedload(Law.children)
    ).order_by(Subject.name, Law.title)
    # =====================================================================
    # <<< FIM DA CORREÇÃO >>>
    # =====================================================================

    # Aplica o filtro de matéria
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
    
    # Note que o template renderizado é "dashboard.html", não "dashboard_atual.html"
    # Certifique-se que o seu arquivo de template se chama `dashboard.html` na pasta `admin`
    return render_template("admin/dashboard.html", 
                           subjects_with_diplomas=subjects_with_diplomas,
                           pending_users_count=pending_users_count,
                           active_announcements_count=active_announcements_count,
                           all_subjects=all_subjects,
                           selected_subject=subject_filter)

# --- O restante do arquivo permanece exatamente como na versão anterior, ---
# --- pois a lógica de adicionar, editar e deletar já estava correta. ---

@admin_bp.route("/subjects", methods=["GET", "POST"])
@login_required
@admin_required
def manage_subjects():
    if request.method == "POST":
        subject_name = request.form.get("name")
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
    subjects = Subject.query.order_by(Subject.name).all()
    normative_acts = Law.query.filter(Law.parent_id.is_(None)).order_by(Law.title).all()

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        content = request.form.get("content")
        subject_id = request.form.get("subject_id")
        parent_id = request.form.get("parent_id")
        audio_url = request.form.get("audio_url")

        if not title:
            flash("O Título é obrigatório.", "danger")
            return render_template("admin/add_edit_law.html", law=None, subjects=subjects, normative_acts=normative_acts)

        new_law = Law(
            title=title, 
            description=description, 
            content=content,
            audio_url=audio_url if audio_url else None
        )
        
        new_law.subject_id = int(subject_id) if subject_id and subject_id != "None" else None
        new_law.parent_id = int(parent_id) if parent_id and parent_id != "" else None
            
        db.session.add(new_law)
        db.session.flush()

        index = 0
        while f'link-{index}-title' in request.form:
            link_title = request.form.get(f'link-{index}-title')
            link_url = request.form.get(f'link-{index}-url')
            if link_title and link_url:
                new_link = UsefulLink(title=link_title, url=link_url, law_id=new_law.id)
                db.session.add(new_link)
            index += 1
        
        db.session.commit()
        flash("Item de estudo adicionado com sucesso!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/add_edit_law.html", law=None, subjects=subjects, normative_acts=normative_acts)

@admin_bp.route("/laws/edit/<int:law_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_law(law_id):
    law = Law.query.get_or_404(law_id)
    subjects = Subject.query.order_by(Subject.name).all()
    normative_acts = Law.query.filter(Law.parent_id.is_(None), Law.id != law_id).order_by(Law.title).all()

    if request.method == "POST":
        law.title = request.form.get("title")
        law.description = request.form.get("description")
        law.content = request.form.get("content")
        subject_id = request.form.get("subject_id")
        parent_id = request.form.get("parent_id")
        audio_url = request.form.get("audio_url")

        if not law.title:
            flash("O Título é obrigatório.", "danger")
            return render_template("admin/add_edit_law.html", law=law, subjects=subjects, normative_acts=normative_acts)

        law.subject_id = int(subject_id) if subject_id and subject_id != "None" else None
        law.parent_id = int(parent_id) if parent_id and parent_id != "" else None
        law.audio_url = audio_url if audio_url else None

        UsefulLink.query.filter_by(law_id=law.id).delete()
        index = 0
        while f'link-{index}-title' in request.form:
            link_title = request.form.get(f'link-{index}-title')
            link_url = request.form.get(f'link-{index}-url')
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
        flash("Item e todos os seus dados relacionados (sub-tópicos, progresso, etc) foram excluídos!", "success")
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
    if user.role == "admin":
        flash("Não é possível alterar o status de um administrador.", "danger")
    else:
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
        try:
            db.session.delete(user)
            db.session.commit()
            flash(f"Usuário {email} e seus dados foram excluídos com sucesso!", "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao excluir o usuário {email}: {e}", "danger")
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
        title = request.form.get("title")
        content = request.form.get("content")
        is_active = request.form.get("is_active") == "on"
        is_fixed = request.form.get("is_fixed") == "on"
        announcement_id = request.form.get("announcement_id")
        if not title or not content:
            flash("Título e conteúdo são obrigatórios.", "danger")
        else:
            if announcement_id:
                announcement = Announcement.query.get_or_404(int(announcement_id))
                announcement.title, announcement.content, announcement.is_active, announcement.is_fixed = title, content, is_active, is_fixed
                flash("Aviso atualizado com sucesso!", "success")
            else:
                new_announcement = Announcement(title=title, content=content, is_active=is_active, is_fixed=is_fixed)
                db.session.add(new_announcement)
                flash("Aviso adicionado com sucesso!", "success")
            db.session.commit()
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
    return redirect(url_for("admin.manage_announcements"))

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
    return redirect(url_for("admin.manage_announcements"))
