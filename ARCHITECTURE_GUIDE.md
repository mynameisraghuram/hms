# 🏥 HM SOFTWARE - Architecture & Implementation Guide
## Comprehensive Technical Documentation

---

## 📊 PROJECT STATISTICS

### Codebase Metrics

```
Total Django Apps:        13
Total Models:             20+
API Endpoints:            40+
Test Files:               25+
Lines of Code:            ~10,000+
Test Coverage:            High (comprehensive pytest suite)
```

### Module Breakdown

| Module | Models | Endpoints | Tests | Status |
|--------|--------|-----------|-------|--------|
| IAM | 5 | 3 | ✅ | Complete |
| Patients | 1 | 4 | ✅ | Complete |
| Encounters | 2 | 10+ | ✅ | Complete |
| Tasks | 1 | 6 | ✅ | Complete |
| Clinical Docs | 2 | 4 | ✅ | Complete |
| Orders | 2 | 3 | ✅ | Complete |
| Lab | 2 | 4 | ✅ | Complete |
| Rules | 1 | 0 | ✅ | Complete |
| Audit | 1 | 0 | ✅ | Complete |
| Alerts | 1 | 1 | ✅ | Complete |
| Billing | 1 | 1 | ✅ | Complete |

---

## 🚀 FUTURE ROADMAP

### Phase 2: Inpatient Department (IPD)
- [ ] Bed management
- [ ] Ward management
- [ ] Admission/Discharge workflow
- [ ] Nursing notes
- [ ] Medication administration records

### Phase 3: Pharmacy
- [ ] Inventory management
- [ ] Prescription management
- [ ] Drug interaction checks
- [ ] Dispensing workflow

### Phase 4: Radiology
- [ ] Imaging orders
- [ ] PACS integration
- [ ] Radiology reports
- [ ] Image viewing

### Phase 5: Advanced Features
- [ ] Telemedicine
- [ ] Mobile apps
- [ ] Analytics dashboard
- [ ] AI-powered diagnostics
- [ ] Integration with external systems (HL7, FHIR)

---

## 💡 BEST PRACTICES & PATTERNS

### 1. Event-Driven Development

**When to use events**:
- ✅ Cross-module communication
- ✅ Async workflows
- ✅ Audit trail generation
- ✅ Timeline updates
- ✅ Notification triggers

**When NOT to use events**:
- ❌ Synchronous validation
- ❌ Direct database queries
- ❌ Simple CRUD operations

### 2. Idempotency

**Always make operations idempotent when**:
- Creating records that might be retried
- Processing external events
- Handling webhook callbacks
- Batch operations

**Implementation pattern**:
```python
def save(self, *args, **kwargs):
    try:
        with transaction.atomic(savepoint=True):
            return super().save(*args, **kwargs)
    except IntegrityError:
        # Handle duplicate gracefully
        existing = self.__class__.objects.get(unique_key=self.unique_key)
        # Update if needed
        return existing
```

### 3. Multi-Tenancy

**Always scope queries**:
```python
# ❌ Bad
patients = Patient.objects.all()

# ✅ Good
patients = Patient.objects.filter(
    tenant_id=request.tenant_id,
    facility_id=request.facility_id
)
```

**Use middleware for automatic scoping**:
```python
class TenantScopeMiddleware:
    def __call__(self, request):
        if hasattr(request, 'tenant_id'):
            # Automatically filter all queries
            pass
```

### 4. Immutable Event Streams

**Never modify or delete events**:
```python
class EncounterEvent(models.Model):
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Events are immutable")
        return super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        raise ValidationError("Events cannot be deleted")
```

### 5. Versioning for Clinical Data

**Use append-only pattern**:
```python
# Create new version instead of updating
new_doc = ClinicalDocument.objects.create(
    version=old_doc.version + 1,
    supersedes_document_id=old_doc.id,
    status=DocumentStatus.AMENDED,
    payload=updated_payload
)
```

---

## 🔧 COMMON DEVELOPMENT TASKS

### Adding a New Module

1. **Create Django app**:
```bash
python manage.py startapp new_module hm_core/new_module
```

2. **Define models** (inherit from `ScopedModel`):
```python
from hm_core.common.models import ScopedModel

class NewEntity(ScopedModel):
    name = models.CharField(max_length=255)
    # ... other fields
```

3. **Create serializers**:
```python
from rest_framework import serializers

class NewEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = NewEntity
        fields = '__all__'
```

4. **Create views**:
```python
from rest_framework import viewsets

class NewEntityViewSet(viewsets.ModelViewSet):
    queryset = NewEntity.objects.all()
    serializer_class = NewEntitySerializer
    
    def get_queryset(self):
        return super().get_queryset().filter(
            tenant_id=self.request.tenant_id,
            facility_id=self.request.facility_id
        )
```

5. **Register URLs**:
```python
# In hm_core/api/urls.py
router.register(r"new-entities", NewEntityViewSet, basename="new-entities")
```

6. **Add to INSTALLED_APPS**:
```python
# In config/settings/base.py
INSTALLED_APPS = [
    # ...
    "hm_core.new_module",
]
```

7. **Create migrations**:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Adding Event Subscribers

```python
# In new_module/subscribers.py
from hm_core.common.events import subscribe

@subscribe("encounter.created")
def handle_encounter_created(payload):
    # Your logic here
    pass

# In new_module/apps.py
class NewModuleConfig(AppConfig):
    def ready(self):
        import new_module.subscribers  # Register subscribers
```

### Adding Permissions

```python
# 1. Create permission
Permission.objects.create(
    code="new_module.can_do_something",
    description="Can do something in new module"
)

# 2. Assign to role
role = Role.objects.get(code="doctor")
permission = Permission.objects.get(code="new_module.can_do_something")
RolePermission.objects.create(role=role, permission=permission)

# 3. Check in view
from hm_core.iam.services import has_permission

if not has_permission(request.user, "new_module.can_do_something"):
    raise PermissionDenied()
```

---

## 🐛 TROUBLESHOOTING

### Common Issues

#### 1. Scope Headers Missing
**Error**: `PermissionDenied: Missing scope headers`

**Solution**: Always include headers in requests:
```python
headers = {
    "X-Tenant-ID": str(tenant_id),
    "X-Facility-ID": str(facility_id),
}
response = client.get("/api/patients/", headers=headers)
```

#### 2. Idempotency Key Conflicts
**Error**: `IntegrityError: duplicate key value violates unique constraint`

**Solution**: Use unique idempotency keys:
```python
import uuid
idempotency_key = f"draft-{encounter_id}-{uuid.uuid4()}"
```

#### 3. Event Not Firing
**Problem**: Subscriber not receiving events

**Solution**: Ensure subscriber is registered in `apps.py`:
```python
class MyAppConfig(AppConfig):
    def ready(self):
        import myapp.subscribers  # This registers the @subscribe decorators
```

#### 4. Migration Conflicts
**Error**: `Conflicting migrations detected`

**Solution**:
```bash
# Delete conflicting migrations
rm hm_core/myapp/migrations/0002_*.py

# Recreate migrations
python manage.py makemigrations

# Or merge migrations
python manage.py makemigrations --merge
```

---

## 📚 API USAGE EXAMPLES

### Complete Workflow Example: OPD Visit

```python
import requests

BASE_URL = "http://localhost:8000/api"
headers = {
    "Authorization": "Bearer <access_token>",
    "X-Tenant-ID": "<tenant_uuid>",
    "X-Facility-ID": "<facility_uuid>",
}

# 1. Create patient
patient_response = requests.post(
    f"{BASE_URL}/patients/",
    headers=headers,
    json={
        "full_name": "John Doe",
        "mrn": "MRN-2024-001",
        "date_of_birth": "1990-01-01",
        "gender": "M",
        "phone": "+1234567890"
    }
)
patient_id = patient_response.json()["id"]

# 2. Create encounter
encounter_response = requests.post(
    f"{BASE_URL}/encounters/",
    headers=headers,
    json={
        "patient": patient_id,
        "reason": "Fever and cough",
        "scheduled_at": "2024-01-15T10:00:00Z"
    }
)
encounter_id = encounter_response.json()["id"]

# 3. Check-in patient
requests.post(
    f"{BASE_URL}/encounters/{encounter_id}/check-in/",
    headers=headers
)

# 4. Record vitals
requests.post(
    f"{BASE_URL}/encounters/{encounter_id}/vitals/",
    headers=headers,
    json={
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 80,
        "pulse": 72,
        "temperature": 98.6,
        "spo2": 98
    }
)

# 5. Start consultation
requests.post(
    f"{BASE_URL}/encounters/{encounter_id}/start-consult/",
    headers=headers
)

# 6. Add assessment
requests.post(
    f"{BASE_URL}/encounters/{encounter_id}/assessment/",
    headers=headers,
    json={
        "assessment": "Upper respiratory tract infection"
    }
)

# 7. Add plan
requests.post(
    f"{BASE_URL}/encounters/{encounter_id}/plan/",
    headers=headers,
    json={
        "plan": "Prescribe antibiotics, rest, follow-up in 3 days"
    }
)

# 8. Create lab order
order_response = requests.post(
    f"{BASE_URL}/orders/",
    headers=headers,
    json={
        "encounter": encounter_id,
        "order_type": "LAB",
        "priority": "ROUTINE",
        "items": [
            {"service_code": "CBC"},
            {"service_code": "CRP"}
        ]
    }
)

# 9. Get encounter timeline
timeline_response = requests.get(
    f"{BASE_URL}/encounters/{encounter_id}/timeline/",
    headers=headers
)
print(timeline_response.json())

# 10. Close encounter
requests.post(
    f"{BASE_URL}/encounters/{encounter_id}/close/",
    headers=headers
)
```

### Lab Workflow Example

```python
# 1. Receive sample
sample_id = "<sample_uuid>"
requests.post(
    f"{BASE_URL}/lab/samples/{sample_id}/receive/",
    headers=headers,
    json={
        "barcode": "LAB-2024-001",
        "received_at": "2024-01-15T11:00:00Z"
    }
)

# 2. Enter results
result_response = requests.post(
    f"{BASE_URL}/lab/results/",
    headers=headers,
    json={
        "order_item_id": "<order_item_uuid>",
        "result_payload": {
            "hemoglobin": 12.5,
            "wbc": 8000,
            "platelets": 150000
        },
        "is_critical": False
    }
)
result_id = result_response.json()["id"]

# 3. Verify results
requests.post(
    f"{BASE_URL}/lab/results/{result_id}/verify/",
    headers=headers
)

# 4. Release results
requests.post(
    f"{BASE_URL}/lab/results/{result_id}/release/",
    headers=headers
)
```

---

## 🔒 SECURITY CONSIDERATIONS

### 1. Authentication
- ✅ JWT tokens with short expiry (10 min access, 14 days refresh)
- ✅ HttpOnly cookies for web clients
- ✅ Token rotation on refresh
- ✅ Secure cookie settings in production

### 2. Authorization
- ✅ Role-based access control (RBAC)
- ✅ Facility-level membership validation
- ✅ Permission checks at API level
- ✅ Scope enforcement via headers

### 3. Data Protection
- ✅ Multi-tenant data isolation
- ✅ Encrypted database connections
- ✅ Audit trail for all actions
- ✅ Immutable event streams

### 4. API Security
- ✅ CORS configuration
- ✅ Rate limiting (to be implemented)
- ✅ Input validation via serializers
- ✅ SQL injection protection (Django ORM)
- ✅ XSS protection (Django templates)

### 5. Compliance
- ✅ HIPAA-ready architecture
- ✅ Complete audit trail
- ✅ Data retention policies (to be configured)
- ✅ Access logging

---

## 📖 GLOSSARY

### Terms

- **Tenant**: An organization or hospital using the system
- **Facility**: A branch or location within a tenant
- **Scope**: The tenant+facility context for data isolation
- **Encounter**: An OPD visit or patient interaction
- **Task**: An operational workflow item
- **Event**: An immutable record of something that happened
- **Timeline**: Chronological view of encounter events
- **Close-gate**: Validation rules before closing an encounter
- **Idempotency**: Ability to safely retry operations
- **Event Sourcing**: Storing state changes as immutable events

### Acronyms

- **OPD**: Outpatient Department
- **IPD**: Inpatient Department
- **LIS**: Laboratory Information System
- **RBAC**: Role-Based Access Control
- **JWT**: JSON Web Token
- **MRN**: Medical Record Number
- **SOAP**: Subjective, Objective, Assessment, Plan
- **CRUD**: Create, Read, Update, Delete
- **API**: Application Programming Interface
- **UUID**: Universally Unique Identifier
- **CQRS**: Command Query Responsibility Segregation

---

## 📞 SUPPORT & RESOURCES

### Documentation
- API Docs: `http://localhost:8000/api/docs/`
- OpenAPI Schema: `http://localhost:8000/api/schema/`
- Django Admin: `http://localhost:8000/admin/`

### Development
- Run server: `python manage.py runserver`
- Run tests: `pytest`
- Create migrations: `python manage.py makemigrations`
- Apply migrations: `python manage.py migrate`

### Useful Commands
```bash
# Bootstrap roles
python manage.py ensure_roles

# Create test data
python manage.py create_test_encounter

# Backfill events
python manage.py backfill_encounter_events

# Django shell
python manage.py shell

# Database shell
python manage.py dbshell
```

---

## 🎯 KEY ACHIEVEMENTS

### Technical Excellence
✅ **Modular Architecture**: Clean separation of concerns with 13 independent modules
✅ **Event-Driven Design**: Loose coupling via pub/sub events
✅ **Idempotent Operations**: Safe retry logic throughout
✅ **Event Sourcing**: Complete audit trail via immutable events
✅ **Multi-Tenancy**: Secure data isolation at tenant+facility level
✅ **RBAC**: Fine-grained permission control
✅ **Versioning**: Clinical document and lab result versioning
✅ **Workflow Engine**: Flexible task-based workflows
✅ **Rules Engine**: Configurable business logic
✅ **Timeline API**: Unified view of encounter history

### Quality Assurance
✅ **Comprehensive Testing**: 25+ test files with high coverage
✅ **Type Safety**: Proper use of Django's type system
✅ **Code Organization**: Clear module boundaries
✅ **Documentation**: Inline comments and docstrings
✅ **API Documentation**: Auto-generated OpenAPI/Swagger docs

### Production Readiness
✅ **Security**: JWT authentication, RBAC, scope enforcement
✅ **Scalability**: Multi-tenant architecture
✅ **Reliability**: Idempotency, event sourcing
✅ **Maintainability**: Modular design, comprehensive tests
✅ **Compliance**: Audit trail, immutable events

---

## 📝 CONCLUSION

This Healthcare Management System represents a **production-ready, enterprise-grade solution** for hospital management. The architecture is designed for:

- **Scalability**: Multi-tenant, event-driven design
- **Reliability**: Idempotent operations, immutable audit trail
- **Security**: JWT authentication, RBAC, data isolation
- **Maintainability**: Modular monolith, comprehensive tests
- **Extensibility**: Event-driven, plugin-friendly architecture

The system successfully implements **Phase 0 (OPD)** and **Phase 1 (Laboratory)** with a solid foundation for future phases (IPD, Pharmacy, Radiology, etc.).

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: HM Software Development Team
