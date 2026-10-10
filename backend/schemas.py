from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import Literal, Optional
from datetime import date, datetime

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Record(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
class TicketSummary(BaseModel):
    total: int
    new: int
    active: int
class TicketProjectOption(BaseModel):
    id: str
    code: str
    name: str
class Login(Input):
    username: str
    password: str
    captcha_id: str = ''
    captcha_answer: str = ''
    recaptcha_token: str = ''
    remember: bool = False
class PasswordChange(Input):
    current_password: str
    new_password: str = Field(min_length=10, max_length=72)
class ClientInput(Input):
    name: str = Field(min_length=2, max_length=150)
    contact: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str = ''
    industry: str = ''
    address: str = ''
class UserInput(Input):
    name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_.-]+$')
    email: EmailStr
    role: Literal['Admin','Admin Project','Developer','Accounting','Client']
    client_id: str = ''
    whatsapp_number: str = Field(default='', max_length=30)
class UserUpdate(Input):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    username: Optional[str] = Field(default=None, min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_.@-]+$')
    email: Optional[EmailStr] = None
    whatsapp_number: Optional[str] = Field(default=None, max_length=30)
    role: Optional[Literal['Admin','Admin Project','Developer','Accounting','Client']] = None
    active: Optional[bool] = None
    client_id: Optional[str] = None
    new_password: Optional[str] = Field(default=None, min_length=10, max_length=72)
class ProjectInput(Input):
    name: str = Field(min_length=3, max_length=150)
    client_id: str
    description: str = ''
    platforms: list[str] = Field(min_length=1)
    category: str = ''
    type: Literal['Kecil','Besar'] = 'Besar'
    value: float = Field(default=0, ge=0)
    start_date: date
    due_date: date
    assigned_to: list[str] = []
    internal_notes: str = ''
    @model_validator(mode='after')
    def check_dates(self):
        if self.due_date < self.start_date: raise ValueError('Deadline harus setelah tanggal mulai.')
        self.platforms = [p.strip() for p in self.platforms if p.strip()]
        if not self.platforms: raise ValueError('Pilih minimal satu platform.')
        self.category = ', '.join(self.platforms)
        return self
class StatusInput(Input):
    status: str
    note: str = Field(default='', max_length=1000)
class FeatureInput(Input):
    name: str = Field(min_length=2, max_length=150)
    category: Literal['Frontend','Backend','UI/UX','Lainnya'] = 'Frontend'
    price: float = Field(default=0, ge=0)
    assigned_to: str = ''
    due_date: Optional[date] = None
class ProgressInput(Input):
    status: Literal['Belum dimulai','Dikerjakan','Selesai']
class CostInput(Input):
    development_cost: float = Field(ge=0)
    server_cost: float = Field(ge=0)
class WorkInput(Input):
    title: str = Field(min_length=3, max_length=200)
    description: str = ''
    kind: str
    assigned_to: str = ''
    entry_date: Optional[date] = None
    started_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: Literal['Rendah','Sedang','Tinggi','Mendesak'] = 'Sedang'
    estimate: float = Field(default=0, ge=0)
    subtasks: list[str] = []
ServerStage = Literal['Belum Naik','Dev Server','Production']
Priority = Literal['Rendah','Sedang','Tinggi','Mendesak']
StatusKind = Literal['todo','active','done']
class TaskInput(Input):
    list_id: str = ''
    sprint_id: str = ''
    milestone: bool = False
    custom_fields: dict = Field(default_factory=dict)
    reminder_at: Optional[datetime] = None
    title: str = Field(min_length=1, max_length=200)
    description: str = ''
    status: str = 'Belum Mulai'
    server: ServerStage = 'Belum Naik'
    assigned_to: str = ''
    assignee_ids: Optional[list[str]] = Field(default=None, max_length=30)
    dependencies: list[str] = Field(default_factory=list, max_length=100)
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: Priority = 'Sedang'
    tags: list[str] = []
    estimate_hours: float = Field(default=0, ge=0)
    subtasks: list[str] = []
class TaskUpdate(Input):
    description_html: Optional[str] = Field(default=None, max_length=200000)
    list_id: Optional[str] = None
    sprint_id: Optional[str] = None
    milestone: Optional[bool] = None
    custom_fields: Optional[dict] = None
    reminder_at: Optional[datetime] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    server: Optional[ServerStage] = None
    assigned_to: Optional[str] = None
    assignee_ids: Optional[list[str]] = Field(default=None, max_length=30)
    dependencies: Optional[list[str]] = Field(default=None, max_length=100)
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: Optional[Priority] = None
    tags: Optional[list[str]] = None
    estimate_hours: Optional[float] = Field(default=None, ge=0)
    order: Optional[float] = None
class SubtaskInput(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=3000)
    assigned_to: str = ''
class SubtaskUpdate(Input):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=3000)
    description_html: Optional[str] = Field(default=None, max_length=200000)
    done: Optional[bool] = None
    assigned_to: Optional[str] = None
class StatusColumnInput(Input):
    name: str = Field(min_length=1, max_length=40)
    color: str = Field(default='#87909e', pattern=r'^#[0-9a-fA-F]{6}$')
    kind: StatusKind = 'active'
class StatusColumnUpdate(Input):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    color: Optional[str] = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    kind: Optional[StatusKind] = None
class ReorderInput(Input):
    ids: list[str]
class TaskCommentInput(Input):
    message: str = Field(min_length=1, max_length=3000)
    mention_ids: list[str] = Field(default_factory=list, max_length=30)
    assigned_to: str = ''
class TimeEntryInput(Input):
    minutes: int = Field(gt=0, le=1440)
    note: str = ''
    date: Optional[date] = None
class BulkTaskInput(Input):
    list_id: Optional[str] = None
    sprint_id: Optional[str] = None
    ids: list[str] = Field(min_length=1)
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[Priority] = None
    delete: bool = False
CostGroup = Literal['Development','Server','Lainnya']
class CostTypeInput(Input):
    name: str = Field(min_length=2, max_length=100)
    group: CostGroup = 'Lainnya'
    description: str = ''
class CostTypeUpdate(Input):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    group: Optional[CostGroup] = None
    description: Optional[str] = None
    active: Optional[bool] = None
class ExpenseInput(Input):
    cost_type_id: str
    amount: float = Field(gt=0)
    date: date
    note: str = ''
class WorkUpdate(Input):
    status: str
    approved: bool = False
    started_date: Optional[date] = None
    due_date: Optional[date] = None
    priority: Optional[Literal['Rendah','Sedang','Tinggi','Mendesak']] = None
    estimate: Optional[float] = Field(default=None, ge=0)
class DeployInput(Input):
    environment: Literal['Development','Production']
    url: str = Field(pattern=r'^https?://[^\s]+$')
    version: str = Field(min_length=1, max_length=50)
    notes: str = ''
class TicketInput(Input):
    project_id: str
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)
    description_html: str = Field(default='', max_length=20000)
    cc_emails: list[EmailStr] = Field(default=[], max_length=10)
    category: Literal['Bug / Problem','Maintenance','Preventive','Support','Change Request','Out of Scope'] = 'Bug / Problem'
    priority: Literal['Rendah','Sedang','Tinggi','Mendesak'] = 'Sedang'
class TicketUpdate(Input):
    status: str
    category: Optional[Literal['Bug / Problem','Maintenance','Preventive','Support','Change Request','Out of Scope']] = None
    assigned_to: Optional[str] = None
    estimate: Optional[float] = Field(default=None, ge=0)
class CommentInput(Input):
    message: str = Field(min_length=1, max_length=3000)
    internal: bool = False