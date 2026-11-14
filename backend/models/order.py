import uuid
from models.product import now


def build(oid, customer, product, qty, address):
    """Order document. All money values come from the stored product, never from the browser."""
    ts = now()
    return {"orderId": oid, "eventId": uuid.uuid4().hex, "customerId": customer["uid"], "customerName": customer.get("name", ""),
            "productId": product["productId"], "productName": product["productName"], "colour": product.get("colour", ""),
            "imageObjectName": product.get("imageObjectName", ""), "sellerId": product["sellerId"], "quantity": qty,
            "unitPrice": product["price"], "totalAmount": round(product["price"] * qty, 2), "deliveryAddress": address,
            "paymentMethod": "COD", "paymentStatus": "Pending", "orderStatus": "Confirmed", "deliveryStatus": "Pending",
            "deliveredAt": "", "createdAt": ts, "updatedAt": ts, "version": 1, "gcsSyncPending": True,
            "history": [{"status": "Confirmed", "at": ts, "by": customer["uid"]}]}


def service_row(o):
    return {"serviceRecordId": "S-" + o["orderId"], "orderId": o["orderId"], "customerId": o["customerId"], "productId": o["productId"],
            "productName": o["productName"], "sellerId": o["sellerId"], "quantity": o["quantity"], "totalAmount": o["totalAmount"],
            "paymentMethod": o["paymentMethod"], "orderStatus": o["orderStatus"], "paymentStatus": o["paymentStatus"],
            "deliveryStatus": o["deliveryStatus"], "createdAt": o["createdAt"], "updatedAt": o["updatedAt"], "deliveredAt": o["deliveredAt"]}


def queue_row(o):
    return {"queueRecordId": "Q-" + o["orderId"], "orderId": o["orderId"], "customerId": o["customerId"], "productId": o["productId"],
            "quantity": o["quantity"], "paymentMethod": o["paymentMethod"], "queueStatus": "Queued", "deliveryAttempts": 0,
            "lastError": "", "createdAt": o["createdAt"], "processedAt": ""}


def event(o):
    return {"event_id": o["eventId"], "order_id": o["orderId"], "product_id": o["productId"], "customer_id": o["customerId"],
            "quantity": o["quantity"], "payment_method": o["paymentMethod"], "order_status": "Confirmed", "created_at": o["createdAt"]}


def service_api(r):   # PascalCase rows used by the dashboards
    return {"OrderID": r["orderId"], "CustomerID": r["customerId"], "ProductID": r["productId"], "ProductName": r["productName"], "SellerID": r["sellerId"],
            "Quantity": r["quantity"], "TotalAmount": r["totalAmount"], "PaymentMethod": r["paymentMethod"], "OrderStatus": r["orderStatus"],
            "PaymentStatus": r["paymentStatus"], "DeliveryStatus": r["deliveryStatus"], "CreatedAt": r["createdAt"], "UpdatedAt": r["updatedAt"], "DeliveredAt": r["deliveredAt"]}


def queue_api(r):
    return {"OrderID": r["orderId"], "ProductID": r["productId"], "CustomerID": r["customerId"], "Quantity": r["quantity"], "QueueStatus": r["queueStatus"],
            "DequeueCount": r.get("deliveryAttempts", 0), "LastError": r.get("lastError", ""), "CreatedAt": r["createdAt"], "ProcessedAt": r.get("processedAt", "")}
