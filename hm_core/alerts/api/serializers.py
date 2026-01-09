from rest_framework import serializers
from hm_core.alerts.models import Alert, Notification


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = [
            "id",
            "code",
            "title",
            "message",
            "severity",
            "status",
            "encounter_id",
            "task_id",
            "patient_id",
            "lab_result_id",
            "acked_by_user_id",
            "acked_at",
            "created_at",
            "updated_at",
            "meta",
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "channel",
            "is_read",
            "read_at",
            "alert_id",
            "encounter_id",
            "task_id",
            "created_at",
            "meta",
        ]
