from pydantic import BaseModel, Field

class LoginData(BaseModel):
    username: str
    password: str

class PrintRequest(BaseModel):
    repo_id: str = Field(..., max_length=100)
    file_path: str = Field(..., max_length=1000)
    
    # Жесткий белый список символов для защиты CUPS от инъекций
    printer_name: str = Field(..., pattern=r'^[a-zA-Z0-9_\-]+$')
    
    copies: int = Field(default=1, ge=1, le=50)
    pages: str = Field(default="all", max_length=100, pattern=r'^(all|все|ALL|ВСЕ|[\d\s\-,]*)$')
    
    orientation: str = Field(default="portrait", pattern=r'^(portrait|landscape)$')
    margins: str = Field(default="normal", pattern=r'^(normal|narrow|wide|none|default)$')
    paper_size: str = Field(default="a4", pattern=r'^(a4|A4|a3|A3|letter|LETTER)$')
    scale: str = Field(default="fit", max_length=10, pattern=r'^(fit|\d{2,3})$')
    duplex: str = Field(default="none", pattern=r'^(none|two-sided-long-edge|two-sided-short-edge)$')