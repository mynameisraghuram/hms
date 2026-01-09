# backend/hm_core/common/task_codes.py
def short8(uuid_value):
    s = str(uuid_value).replace("-", "")
    return s[:8]


def lab_sample_receive_code(order_item_id):
    return f"lab-sample-receive-{short8(order_item_id)}"


def lab_result_enter_code(order_item_id):
    return f"lab-result-enter-{short8(order_item_id)}"


def lab_result_verify_code(order_item_id):
    return f"lab-result-verify-{short8(order_item_id)}"


def critical_ack_code():
    return "critical-result-ack"
