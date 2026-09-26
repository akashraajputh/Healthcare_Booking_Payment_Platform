from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CentreTest(Base):
    __tablename__ = "centre_tests"
    __table_args__ = (CheckConstraint("price > 0", name="ck_centre_tests_price_positive"),)

    centre_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_centres.id", ondelete="CASCADE"), primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_tests.id", ondelete="CASCADE"), primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    centre: Mapped["Centre"] = relationship(back_populates="tests")
    test: Mapped["DiagnosticTest"] = relationship(back_populates="centres")
