# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from src.models.user import db, User, Announcement, UserSeenAnnouncement 
# ATUALIZADO: Importar UsefulLink
from src.models.law import Law, Subject, UsefulLink 
from src.models.progress import UserProgress 

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Decorator to check for admin role
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
    # ... (código do seu dashboard admin permanece o mesmo) ...
    subject_filter = request.args.get("subject_filter", "all")
    all_subjects = Subject.query.order_by(Subject.name).all()
    subjects_with_laws = []
    laws_without_subject = []
    if subject_filter == "all":
        subjects_with_laws = Subject.query.options(db.joinedload(Subject.laws)).order_by(Subject.name).all()
        laws_without_subject = Law.query.filter(Law.subject_id == None).order_by(Law.title).all()
    elif subject_filter == "none":
        laws_without_subject = Law.query.filter(Law.subject_id == None).order_by(Law.title).all()
    else:
        try:
            subject_id = int(subject_filter)
            subject = Subject.query.options(db.joinedload(Subject.laws)).filter_by(id=subject_id).first()
            if subject:
                subjects_with_laws = [subject]
        except ValueError:
            subjects_with_laws = Subject.query.options(db.joinedload(Subject.laws)).order_by(Subject.name).all()
            laws_without_subject = Law.query.filter(Law.subject_id == None).order_by(Law.title).all()
    pending_users_count = User.query.filter_by(is_approved=False, role="student").count()
    active_announcements_count = Announcement.query.filter_by(is_active=True).count()
    return render_template("admin/dashboard.html", 
                           subjects_with_laws=subjects_with_laws, 
                           laws_without_subject=laws_without_subject, 
                           pending_users_count=pending_users_count,
                           active_announcements_count=active_announcements_count,
                           all_subjects=all_subjects,
                           selected_subject=subject_filter)

# --- Subject Management ---
# ... (suas rotas de gerenciamento de matéria permanecem as mesmas) ...
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
        flash(f"Não é possível excluir a matéria '{subject.name}', pois ela contém leis associadas.", "danger")
    else:
        db.session.delete(subject)
        db.session.commit()
        flash(f"Matéria '{subject.name}' excluída com sucesso!", "success")
    return redirect(url_for("admin.manage_subjects"))


# --- Law Management ---
@admin_bp.route("/laws/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_law():
    subjects = Subject.query.order_by(Subject.name).all()
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        content = request.form.get("content")
        subject_id = request.form.get("subject_id")
        audio_url = request.form.get("audio_url")

        if not title or not content:
            flash("Título e conteúdo são obrigatórios.", "danger")
            return render_template("admin/add_edit_law.html", law=None, subjects=subjects, audio_url=audio_url)

        new_law = Law(
            title=title, 
            description=description, 
            content=content,
            audio_url=audio_url if audio_url else None
        )
        if subject_id and subject_id != "None":
            new_law.subject_id = int(subject_id)
        else:
            new_law.subject_id = None
            
        db.session.add(new_law)

        # --- INÍCIO: LÓGICA PARA ADICIONAR LINKS ÚTEIS ---
        index = 0
        while f'link-{index}-title' in request.form:
            link_title = request.form.get(f'link-{index}-title')
            link_url = request.form.get(f'link-{index}-url')
            if link_title and link_url:
                new_link = UsefulLink(title=link_title, url=link_url, law=new_law)
                db.session.add(new_link)
            index += 1
        # --- FIM DA LÓGICA ---
        
        db.session.commit()
        flash("Lei adicionada com sucesso!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/add_edit_law.html", law=None, subjects=subjects)

@admin_bp.route("/laws/edit/<int:law_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_law(law_id):
    law = Law.query.get_or_404(law_id)
    subjects = Subject.query.order_by(Subject.name).all()
    if request.method == "POST":
        law.title = request.form.get("title")
        law.description = request.form.get("description")
        law.content = request.form.get("content")
        subject_id = request.form.get("subject_id")
        audio_url = request.form.get("audio_url")

        if not law.title or not law.content:
            flash("Título e conteúdo são obrigatórios.", "danger")
            return render_template("admin/add_edit_law.html", law=law, subjects=subjects)

        if subject_id and subject_id != "None":
            law.subject_id = int(subject_id)
        else:
            law.subject_id = None
        law.audio_url = audio_url if audio_url else None

        # --- INÍCIO: LÓGICA PARA ATUALIZAR LINKS ÚTEIS (APAGAR E RECRIAR) ---
        # 1. Apagar links existentes associados a esta lei
        UsefulLink.query.filter_by(law_id=law.id).delete()

        # 2. Adicionar os links enviados pelo formulário
        index = 0
        while f'link-{index}-title' in request.form:
            link_title = request.form.get(f'link-{index}-title')
            link_url = request.form.get(f'link-{index}-url')
            # O ID do link não é necessário aqui, pois estamos recriando
            if link_title and link_url:
                new_link = UsefulLink(title=link_title, url=link_url, law=law)
                db.session.add(new_link)
            index += 1
        # --- FIM DA LÓGICA ---

        db.session.commit()
        flash("Lei atualizada com sucesso!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/add_edit_law.html", law=law, subjects=subjects)


@admin_bp.route("/laws/delete/<int:law_id>", methods=["POST"])
@login_required
@admin_required
def delete_law(law_id):
    # ... (sua rota de deletar lei permanece a mesma) ...
    # A configuração 'cascade' no modelo vai deletar os links automaticamente.
    law = Law.query.get_or_404(law_id)
    try:
        db.session.delete(law)
        db.session.commit()
        flash("Lei e todos os seus dados relacionados (progresso, anotações, links) foram excluídos com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir a lei: {e}", "danger")
        print(f"Error deleting law {law_id}: {e}")
    return redirect(url_for("admin.dashboard"))

# --- User Management ---
# ... (todas as suas outras rotas de admin permanecem as mesmas) ...
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
            print(f"Error deleting user {user_id}: {e}")
    return redirect(url_for("admin.manage_users"))

@admin_bp.route("/users/reset-password/<int:user_id>", methods=["GET", "POST"])
@login_required
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin" and user.id != current_user.id:
        flash("Não é possível redefinir a senha de outro administrador.", "danger")
        return redirect(url_for("admin.manage_users"))
    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        if not new_password:
            flash("A nova senha não pode estar vazia.", "danger")
            return render_template("admin/reset_password.html", user=user)
        if new_password != confirm_password:
            flash("As senhas não coincidem.", "danger")
            return render_template("admin/reset_password.html", user=user)
        user.set_password(new_password)
        try:
            db.session.commit()
            flash(f"Senha do usuário {user.email} redefinida com sucesso!", "success")
            return redirect(url_for("admin.manage_users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao redefinir a senha: {e}", "danger")
            return render_template("admin/reset_password.html", user=user)
    return render_template("admin/reset_password.html", user=user)

# --- Announcement Management ---
# ... (suas rotas de gerenciamento de anúncios permanecem as mesmas) ...
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
            flash("Título e conteúdo do aviso são obrigatórios.", "danger")
        else:
            if announcement_id:
                announcement = Announcement.query.get_or_404(int(announcement_id))
                announcement.title = title
                announcement.content = content
                announcement.is_active = is_active
                announcement.is_fixed = is_fixed
                db.session.commit()
                flash("Aviso atualizado com sucesso!", "success")
            else:
                new_announcement = Announcement(title=title, content=content, is_active=is_active, is_fixed=is_fixed)
                db.session.add(new_announcement)
                db.session.commit()
                flash("Aviso adicionado com sucesso!", "success")
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
        print(f"Error deleting announcement {announcement_id}: {e}")
    return redirect(url_for("admin.manage_announcements"))
