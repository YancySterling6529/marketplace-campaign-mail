import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.marketplace_mail import BuyerUpdate, InfraiClient, SellerAsset, handoff_asset


def main() -> None:
    recipient = os.environ.get("MARKETPLACE_DEMO_EMAIL")
    if not recipient:
        raise SystemExit("Set MARKETPLACE_DEMO_EMAIL before running the demo")
    asset = SellerAsset("Northstar Bikes", "Road bike listing", recipient, "order-1042")
    update = BuyerUpdate("Your marketplace order is moving", "The seller confirmed the asset and is preparing handoff.")
    result = handoff_asset(InfraiClient(), asset, update)
    print(f"message {result.message_id}: buyer update is {result.status}")


if __name__ == "__main__":
    main()
