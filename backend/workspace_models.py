from datetime import date, datetime
from typing import Literal, Any
from pydantic import Field, model_validator
from schemas import Input

class NodeInput(Input):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['space', 'folder', 'list']
    parent_id: str = ''
    color: str = Field(default='#2c63e8', pattern=r'^#[0-9a-fA-F]{6}$')

class FieldInput(Input):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal['text', 'number', 'date', 'dropdown', 'checkbox']
    options: list[str] = Field(default_factory=list, max_length=30)
    visibility: Literal['Internal', 'Client'] = 'Internal'
    @model_validator(mode='after')
    def choices(self):
        self.options = list(dict.fromkeys(x.strip()[:80] for x in self.options if x.strip()))
        if self.kind == 'dropdown' and not self.options:
            raise ValueError('Isi minimal satu pilihan dropdown.')
        return self

class Named(Input):
    name: str = Field(min_length=1, max_length=120)

class ApplyTemplate(Input):
    list_id: str = ''

class SprintInput(Input):
    name: str = Field(min_length=1, max_length=120)
    goal: str = Field(default='', max_length=1000)
    start_date: date
    end_date: date
    status: Literal['planned', 'active', 'completed'] = 'planned'
    @model_validator(mode='after')
    def dates(self):
        if self.end_date < self.start_date: raise ValueError('Akhir sprint harus setelah mulai.')
        return self

class GoalInput(Input):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=1000)
    metric: Literal['tasks', 'number'] = 'tasks'
    target: float = Field(default=100, gt=0, le=1e12)
    current: float = Field(default=0, ge=0, le=1e12)
    unit: str = Field(default='poin', max_length=30)
    task_ids: list[str] = Field(default_factory=list, max_length=500)
    due_date: date | None = None

class CapacityInput(Input):
    user_id: str
    hours: float = Field(ge=0, le=168)

class DocInput(Input):
    title: str = Field(min_length=1, max_length=150)
    content: str = Field(default='', max_length=150000)
    visibility: Literal['Internal', 'Client'] = 'Internal'
    version: int = Field(default=0, ge=0)

class WhiteboardInput(Input):
    name: str = Field(default='Whiteboard project', min_length=1, max_length=120)
    nodes: list[dict[str, Any]] = Field(default_factory=list, max_length=300)
    edges: list[dict[str, Any]] = Field(default_factory=list, max_length=600)
    version: int = Field(default=0, ge=0)

class AutomationInput(Input):
    name: str = Field(min_length=1, max_length=120)
    trigger: Literal['task_created', 'status_changed']
    condition_field: Literal['', 'status', 'priority'] = ''
    condition_value: str = Field(default='', max_length=100)
    action: Literal['set_status', 'set_priority', 'assign', 'add_tag', 'notify']
    action_value: str = Field(min_length=1, max_length=200)
    enabled: bool = True

class ScheduleInput(Input):
    frequency: Literal['daily', 'weekly', 'monthly'] = 'weekly'
    next_run: datetime
    end_at: datetime | None = None
    enabled: bool = True
    @model_validator(mode='after')
    def dates(self):
        if not self.next_run.tzinfo: raise ValueError('Waktu harus menyertakan zona waktu.')
        if self.end_at and (not self.end_at.tzinfo or self.end_at < self.next_run):
            raise ValueError('Batas pengulangan harus setelah jadwal pertama dan memiliki zona waktu.')
        return self

class CommentResolve(Input):
    resolved: bool