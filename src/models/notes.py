# Em src/models/notes.py

from src.models.user import db
import datetime

class UserNotes(db.Model):
    # ... (seu código de UserNotes permanece inalterado) ...
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = db.relationship("User", backref=db.backref("notes", lazy=True, cascade="all, delete-orphan"))
    law = db.relationship("Law", backref=db.backref("law_notes", lazy=True, cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("user_id", "law_id", name="_user_law_notes_uc"),)
    def __repr__(self):
        return f"<UserNotes User: {self.user_id} Law: {self.law_id}>"


# =====================================================================
# <<< INÍCIO: MODELO UserLawMarkup OTIMIZADO >>>
# Substitua sua classe UserLawMarkup antiga por esta.
# =====================================================================
class UserLawMarkup(db.Model):
    __tablename__ = 'user_law_markup'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Novos campos para salvar apenas a "diferença"
    type = db.Column(db.String(20), nullable=False)  # 'highlight' ou 'bold'
    start_container_path = db.Column(db.String(255), nullable=False)
    start_offset = db.Column(db.Integer, nullable=False)
    end_container_path = db.Column(db.String(255), nullable=False)
    end_offset = db.Column(db.Integer, nullable=False)
    
    # Relações para fácil acesso
    user = db.relationship("User", backref=db.backref("markups", lazy='dynamic', cascade="all, delete-orphan"))
    law = db.relationship("Law", backref=db.backref("markups", lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<UserLawMarkup ID: {self.id} Type: {self.type}>"
# =====================================================================
# <<< FIM: MODELO UserLawMarkup OTIMIZADO >>>
# =====================================================================
