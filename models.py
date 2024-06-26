from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, TIMESTAMP, Uuid, Enum, Table, Column, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs
import datetime
import uuid
from enum import Enum as pyEnum


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = 'profiles'

    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), default=uuid.uuid4,
                                                  primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=True)
    password: Mapped[str]
    location: Mapped[str] = mapped_column(String(200), nullable=True)
    short_intro: Mapped[str] = mapped_column(String(200), nullable=True)
    bio: Mapped[str] = mapped_column(nullable=True)
    profile_image: Mapped[str] = mapped_column(nullable=True,
                                               default='/static/images/default.jpg')
    github: Mapped[str] = mapped_column(String(200), nullable=True)
    x: Mapped[str] = mapped_column(String(200), nullable=True)
    linkedin: Mapped[str] = mapped_column(String(200), nullable=True)
    youtube: Mapped[str] = mapped_column(String(200), nullable=True)
    website: Mapped[str] = mapped_column(String(200), nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.datetime.now(datetime.timezone.utc))

    projects: Mapped[list['Project']] = relationship(back_populates='owner')
    reviews: Mapped[list['Review']] = relationship(back_populates='owner')
    skills: Mapped[list['Skill']] = relationship(
        back_populates='owner', cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = 'skills'

    skill_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), default=uuid.uuid4,
                                                primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(nullable=True)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('profiles.profile_id', ondelete='CASCADE'))

    owner: Mapped[Profile] = relationship(back_populates='skills')


class Message(Base):
    __tablename__ = 'messages'

    message_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), default=uuid.uuid4,
                                                  primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=True)
    body: Mapped[str]
    is_read: Mapped[bool] = mapped_column(default=False)
    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.datetime.now(datetime.timezone.utc))

    sender: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('profiles.profile_id', ondelete='SET NULL'), nullable=True, index=True)
    recipient: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('profiles.profile_id', ondelete='SET NULL'), nullable=True, index=True)


project_tag = Table('project_tag', Base.metadata,
                    Column('project_id', Uuid(as_uuid=True), ForeignKey(
                        'projects.project_id')),
                    Column('tag_id', Uuid(as_uuid=True), ForeignKey('tags.tag_id')))


class Project(Base):
    __tablename__ = 'projects'

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), default=uuid.uuid4,
                                                  primary_key=True, index=True)
    title: Mapped[str] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(nullable=True)
    featured_image: Mapped[str] = mapped_column(nullable=True,
                                                default='/static/images/default.jpg')
    demo_link: Mapped[str] = mapped_column(nullable=True)
    source_code: Mapped[str] = mapped_column(nullable=True)
    vote_total: Mapped[int] = mapped_column(default=0)
    vote_ratio: Mapped[float] = mapped_column(default=0)
    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.datetime.now(datetime.timezone.utc)
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('profiles.profile_id', ondelete='SET NULL'), nullable=True)

    owner: Mapped['Profile'] = relationship(back_populates='projects')
    tags: Mapped[list['Tag']] = relationship(
        back_populates='projects', secondary=project_tag)
    reviews: Mapped[list['Review']] = relationship(back_populates='project')

    def update_vote_ratio(self, value):
        self.vote_ratio = value / self.vote_total * 100


class Review(Base):
    class Value(pyEnum):
        up = 'Up Vote'
        down = 'Down Vote'

    __tablename__ = 'reviews'

    review_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), default=uuid.uuid4,
                                                 primary_key=True, index=True)
    body: Mapped[str] = mapped_column(nullable=True)
    value: Mapped[Value] = mapped_column(Enum(Value), default=Value.up)
    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.datetime.now(datetime.timezone.utc)
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True),
                                                ForeignKey('profiles.profile_id', ondelete='SET NULL'), nullable=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True),
                                                  ForeignKey('projects.project_id', ondelete="CASCADE"), index=True)

    owner: Mapped[Profile] = relationship(back_populates='reviews')
    project: Mapped[Project] = relationship(back_populates='reviews')

    __table_args__ = (UniqueConstraint(
        'project_id', 'owner_id', name='_project_user_uc'),)


class Tag(Base):
    __tablename__ = 'tags'

    tag_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), default=uuid.uuid4,
                                              primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)

    projects: Mapped[list['Tag']] = relationship('Project',
                                                 back_populates='tags', secondary=project_tag)
