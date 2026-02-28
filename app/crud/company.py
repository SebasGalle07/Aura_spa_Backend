from sqlalchemy.orm import Session

from app.models.company import CompanyData
from app.schemas.company import CompanyUpdate, BrandingUpdate


def get_company(db: Session):
    return db.get(CompanyData, 1)


def get_or_create_company(db: Session):
    company = get_company(db)
    if company is None:
        company = CompanyData(id=1)
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


def update_company(db: Session, company: CompanyData, data: CompanyUpdate):
    payload = data.model_dump(exclude_unset=True, by_alias=False)
    for field, value in payload.items():
        setattr(company, field, value)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def update_branding(db: Session, company: CompanyData, data: BrandingUpdate):
    payload = data.model_dump(exclude_unset=True, by_alias=False)
    if "sp_logo" in payload:
        company.sp_logo = payload["sp_logo"]
    landing = payload.get("landing_images")
    if landing is not None:
        if "section1" in landing:
            company.landing_section1 = landing["section1"]
        if "section2" in landing:
            company.landing_section2 = landing["section2"]
        if "section3" in landing:
            company.landing_section3 = landing["section3"]
    db.add(company)
    db.commit()
    db.refresh(company)
    return company
