# -*- coding: utf-8 -*-
from src.models.user import db
import datetime

class UserNotes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Define relationships
    user = db.relationship("User", backref=db.backref("notes", lazy=True))
    law = db.relationship("Law", backref=db.backref("notes", lazy=True))

    # Unique constraint to prevent duplicate notes entries for the same user and law
    __table_args__ = (db.UniqueConstraint("user_id", "law_id", name="_user_law_notes_uc"),)

    def __repr__(self):
        return f"<UserNotes User: {self.user_id} Law: {self.law_id}>"
