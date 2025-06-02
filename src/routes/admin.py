# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from src.models.user import db, User, Announcement # Import User and Announcement models
from src.models.law import Law, Subject # Import Subject model
from src.models.progress import UserProgress # Import UserProgress model

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
    # Group laws by subject for better overview
    subjects_with_laws = Subject.query.options(db.joinedload(Subject.laws)).order_by(Subject.name).all()
    laws_without_subject = Law.query.filter(Law.subject_id == None).order_by(Law.title).all()
    pending_users_count = User.query.filter_by(is_approved=False, role="student").count()
    active_announcements_count = Announcement.query.filter_by(is_active=True).count() # Count active announcements
    return render_template("admin/dashboard.html", 
                           subjects_with_laws=subjects_with_laws, 
                           laws_without_subject=laws_without_subject, 
                           pending_users_count=pending_users_count,
                           active_announcements_count=active_announcements_count) # Pass count to template

# --- Subject Management ---
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
                flash(f"Matéria ", "success")
            else:
                flash(f"Matéria ", "warning")
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
    # Optional: Check if laws are associated and decide how to handle (e.g., prevent deletion or set laws' subject_id to null)
    if subject.laws:
        flash(f"Não é possível excluir a matéria ", "danger")
    else:
        db.session.delete(subject)
        db.session.commit()
        flash(f"Matéria ", "success")
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

        if not title or not content:
            flash("Título e conteúdo são obrigatórios.", "danger")
            return render_template("admin/add_edit_law.html", law=None, subjects=subjects)

        new_law = Law(title=title, description=description, content=content)
        if subject_id and subject_id != "None": # Handle case where no subject is selected
            new_law.subject_id = int(subject_id)
        else:
            new_law.subject_id = None
            
        db.session.add(new_law)
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

        if not law.title or not law.content:
            flash("Título e conteúdo são obrigatórios.", "danger")
            return render_template("admin/add_edit_law.html", law=law, subjects=subjects)

        if subject_id and subject_id != "None":
            law.subject_id = int(subject_id)
        else:
            law.subject_id = None

        db.session.commit()
        flash("Lei atualizada com sucesso!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/add_edit_law.html", law=law, subjects=subjects)

@admin_bp.route("/laws/delete/<int:law_id>", methods=["POST"])
@login_required
@admin_required
def delete_law(law_id):
    law = Law.query.get_or_404(law_id)
    try:
        # Delete related progress records first to avoid foreign key constraint errors
        UserProgress.query.filter_by(law_id=law_id).delete()
        # Now delete the law itself
        db.session.delete(law)
        db.session.commit()
        flash("Lei e progressos relacionados excluídos com sucesso!", "success")
    except Exception as e:
        db.session.rollback() # Rollback in case of error during deletion
        flash(f"Erro ao excluir a lei: {e}", "danger")
        print(f"Error deleting law {law_id}: {e}") # Log the error
    return redirect(url_for("admin.dashboard"))

# --- User Management ---
@admin_bp.route("/users")
@login_required
@admin_required
def manage_users():
    # Fetch all non-admin users
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
        email = user.email # Get email before deleting for the flash message
        try:
            # Delete related progress records first
            UserProgress.query.filter_by(user_id=user_id).delete()
            # Now delete the user
            db.session.delete(user)
            db.session.commit()
            flash(f"Usuário {email} e seus progressos foram excluídos com sucesso!", "warning")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao excluir o usuário {email}: {e}", "danger")
            print(f"Error deleting user {user_id}: {e}") # Log the error
    return redirect(url_for("admin.manage_users"))

# --- Password Reset ---
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
        
        # Atualiza a senha do usuário
        user.set_password(new_password)
        
        try:
            db.session.commit()
            flash(f"Senha do usuário {user.email} redefinida com sucesso!", "success")
            return redirect(url_for("admin.manage_users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao redefinir a senha: {e}", "danger")
            return render_template("admin/reset_password.html", user=user)
    
    # GET request: renderiza o template de redefinição de senha
    return render_template("admin/reset_password.html", user=user)

# --- Update User Source - NOVA FUNCIONALIDADE ---
@admin_bp.route("/users/<int:user_id>/update_source", methods=["POST"])
@login_required
@admin_required
def update_user_source(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.role == "admin":
        flash("Não é possível editar informações de um administrador.", "danger")
        return redirect(url_for("admin.manage_users"))
    
    source = request.form.get("source", "").strip()
    
    # Limitar o tamanho do campo
    if len(source) > 100:
        flash("Origem deve ter no máximo 100 caracteres.", "danger")
        return redirect(url_for("admin.manage_users"))
    
    # Atualizar o campo source
    user.source = source if source else None
    
    try:
        db.session.commit()
        if source:
            flash(f"Origem do usuário {user.email} atualizada para: {source}", "success")
        else:
            flash(f"Origem do usuário {user.email} removida.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao atualizar origem: {e}", "danger")
    
    return redirect(url_for("admin.manage_users"))

# --- Announcement Management ---
@admin_bp.route("/announcements", methods=["GET", "POST"])
@login_required
@admin_required
def manage_announcements():
    if request.method == "POST": # Handle adding new announcement
        title = request.form.get("title")
        content = request.form.get("content")
        is_active = request.form.get("is_active") == "on" # Checkbox value

        if not title or not content:
            flash("Título e conteúdo do aviso são obrigatórios.", "danger")
        else:
            new_announcement = Announcement(title=title, content=content, is_active=is_active)
            db.session.add(new_announcement)
            db.session.commit()
            flash("Aviso adicionado com sucesso!", "success")
        return redirect(url_for("admin.manage_announcements"))

    # GET request: List announcements
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
    flash(f"Aviso ", "success")
    return redirect(url_for("admin.manage_announcements"))

@admin_bp.route("/announcements/delete/<int:announcement_id>", methods=["POST"])
@login_required
@admin_required
def delete_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    flash("Aviso excluído com sucesso!", "success")
    return redirect(url_for("admin.manage_announcements"))

