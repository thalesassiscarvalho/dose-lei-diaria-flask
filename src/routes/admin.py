# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy.orm import joinedload
import datetime
# NOVO: Importar a biblioteca de sanitização e o CSSSanitizer
import bleach
from bleach.css_sanitizer import CSSSanitizer
from src.models.user import db, User, Announcement, UserSeenAnnouncement, LawBanner
from src.models.law import Law, Subject, UsefulLink 
from src.models.progress import UserProgress 

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Definição das regras de sanitização
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

# NOVO: Cria a instância do CSSSanitizer
css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)


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
    # Lógica para buscar os dados para os KPIs (Key Performance Indicators)
    stats = {
        'total_users': User.query.filter_by(role="student").count(),
        'active_users_week': UserProgress.query.filter(UserProgress.last_accessed_at >= (datetime.datetime.utcnow() - datetime.timedelta(days=7))).distinct(UserProgress.user_id).count(),
        'total_laws': Law.query.filter(Law.parent_id.isnot(None)).count(),
    }
    pending_users_count = User.query.filter_by(is_approved=False, role="student").count()

    # --- CORREÇÃO APLICADA AQUI ---
    # O bloco de código abaixo foi comentado porque o modelo User não possui o campo 'created_at'.
    # Isso impede o erro e permite que o dashboard seja carregado.
    #
    # # Lógica para o gráfico de novos usuários (Temporariamente Desativada)
    # new_users_labels = []
    # new_users_values = []
    # for i in range(29, -1, -1):
    #     day = datetime.date.today() - datetime.timedelta(days=i)
    #     # A linha abaixo causa o erro, pois User.created_at não existe
    #     count = User.query.filter(db.func.date(User.created_at) == day, User.role == 'student').count()
    #     new_users_labels.append(day.strftime("%d/%m"))
    #     new_users_values.append(count)

    # Para o gráfico de top conteúdos (exemplo, baseado em visualizações)
    top_content = db.session.query(
        Law.title,
        db.func.count(UserProgress.id).label('views')
    ).join(UserProgress, UserProgress.law_id == Law.id)\
     .filter(Law.parent_id.isnot(None))\
     .group_by(Law.title)\
     .order_by(db.desc('views'))\
     .limit(5).all()

    top_content_labels = [item[0] for item in top_content]
    top_content_values = [item[1] for item in top_content]
    
    charts_data = {
        # Passa uma lista vazia para o gráfico de novos usuários para não quebrar o template
        'new_users': {'labels': [], 'values': []},
        'top_content': {'labels': top_content_labels, 'values': top_content_values}
    }
    
    active_announcements_count = Announcement.query.filter_by(is_active=True).count()


    return render_template("admin/dashboard.html",
                           stats=stats,
                           pending_users_count=pending_users_count,
                           charts_data=charts_data,
                           active_announcements_count=active_announcements_count
                           )

@admin_bp.route('/content-management')
@login_required
@admin_required
def content_management():
    """
    Nova rota dedicada para listar e gerenciar todos os itens de estudo.
    """
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
                           selected_subject=subject_filter,
                           title="Gerenciar Conteúdo")

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
        title = bleach.clean(request.form.get("title", ""), tags=[], strip=True)
        # ALTERADO: Usa o novo css_sanitizer
        description = bleach.clean(request.form.get("description", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        content = bleach.clean(request.form.get("content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        juridiques_explanation = bleach.clean(request.form.get("juridiques_explanation", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer)
        banner_content = bleach.clean(request.form.get("banner_content", ""), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, css_sanitizer=css_sanitizer).strip()
        
        subject_id = request.form.get("subject_id")
        parent_id = request.form.get("parent_id")
        audio_url = bleach.clean(request.form.get("audio_url", ""), tags=[], strip=True)

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
                           pre_selected_parent_id=pre_selected_parent_id)


@admin_bp.route("/laws/edit/<int:law_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_law(law_id):
    law = Law.query.options(joinedload(Law.banner)).get_or_404(law_id)
    subjects = Subject.query.order_by(Subject.name).all()
    normative_acts = Law.query.filter(Law.parent_id.is_(None), Law.id != law_id).order_by(Law.title).all()

    if request.method == "POST":
        law.title = bleach.clean(request.form.get("title"), tags=[], strip=True)
        # ALTERADO: Usa o novo css_sanitizer
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
            return render_template("admin/add_edit_law.html", law=law, subjects=subjects, normative_acts=normative_acts)

        law.subject_id = int(subject_id) if subject_id and subject_id != "None" else None
        law.parent_id = int(parent_id) if parent_id and parent_id != "" else None
        law.audio_url = audio_url if audio_url else None

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
    return redirect(url_for("admin.content_management"))

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
        title = bleach.clean(request.form.get("title"), tags=[], strip=True)
        # ALTERADO: Usa o novo css_sanitizer
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
        UserSeenAnnouncement.query.filter_by(announcement_id=announcement_id).delete()
        db.session.delete(announcement)
        db.session.commit()
        flash("Aviso excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir o aviso: {e}", "danger")
    return redirect(url_for('admin.manage_announcements'))
