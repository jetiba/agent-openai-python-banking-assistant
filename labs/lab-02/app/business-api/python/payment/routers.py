import logging
from fastapi import APIRouter, HTTPException
from models import Payment
from services import PaymentService

logger = logging.getLogger(__name__)
router = APIRouter()

payment_service = PaymentService()


@router.post("/payments")
async def create_payment(payment: Payment):
    """Submit a payment request. The payment is validated, then forwarded
    to the Transaction API as a new transaction record."""
    try:
        payment_service.process_payment(payment)
        return {"status": "ok", "message": f"Payment processed for account {payment.accountId}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error processing payment: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process payment")
