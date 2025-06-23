# src/models/comment.py
from src.extensions import db
import datetime

class UserComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)

    # MODIFICADO: Adicionado ondelete="CASCADE"
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    anchor_paragraph_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship("User", backref="comments")
    # MODIFICADO: Adicionado backref com cascade="all, delete-orphan"
    law = db.relationship("Law", backref=db.backref("comments", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<UserComment {self.id} User: {self.user_id}>"
