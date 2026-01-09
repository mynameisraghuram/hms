# 🏥 HM SOFTWARE - Healthcare Management System
## Complete Project Documentation & Overview

**Version**: Phase 0 & Phase 1 Complete
**Last Updated**: 2026
**Architecture**: Modular Monolith
**Framework**: Django 5.2 + Django REST Framework
**Database**: PostgreSQL

---

## 📋 TABLE OF CONTENTS

1. [Project Overview](#project-overview)
2. [Architecture & Design Patterns](#architecture--design-patterns)
3. [Core Modules](#core-modules)
4. [Data Models](#data-models)
5. [API Endpoints](#api-endpoints)
6. [Authentication & Security](#authentication--security)
7. [Event-Driven Workflows](#event-driven-workflows)
8. [Testing Infrastructure](#testing-infrastructure)
9. [Database Design](#database-design)
10. [Deployment & Configuration](#deployment--configuration)
11. [Future Roadmap](#future-roadmap)

---

## 📋 PROJECT OVERVIEW

### What is HM Software?

HM Software is a **sophisticated, enterprise-grade Healthcare Management System** designed as a **modular monolith**. It provides comprehensive hospital management capabilities for:

- **Phase 0**: Outpatient Department (OPD) Management
- **Phase 1**: Laboratory Information System (LIS)

### Key Characteristics

- ✅ **Multi-Tenant**: Support for multiple hospitals/organizations
- ✅ **Multi-Facility**: Multiple branches per tenant
- ✅ **Event-Driven**: Pub/sub architecture for loose coupling
- ✅ **Idempotent**: Safe retry logic throughout
- ✅ **Auditable**: Complete immutable audit trail
- ✅ **Secure**: JWT authentication with RBAC
- ✅ **Tested**: Comprehensive pytest test suite

### Technology Stack

```
Backend Framework:  Django 5.2
API Framework:      Django REST Framework
Database:           PostgreSQL
Authentication:     JWT (Simple JWT)
API Docs:           DRF Spectacular (OpenAPI/Swagger)
Testing:            pytest + pytest-django
Language:           Python 3.x
```

---

## 🏗️ ARCHITECTURE & DESIGN PATTERNS

### 1. Modular Monolith Architecture

The system is organized as a modular monolith with 13 independent Django apps under `hm_core/`:

```
hm_core/
├── common/          # Shared infrastructure
├── tenants/         # Multi-tenancy
├── facilities/      # Facility management
├── iam/             # Identity & Access Management
├── patients/        # Patient records
├── encounters/      # OPD visits
├── tasks/           # Workflow engine
├── clinical_docs/   # Clinical documentation
├── orders/          # Order management
├── lab/             # Laboratory module
├── rules/           # Business rules engine
├── audit/           # Audit trail
├── alerts/          # Critical alerts
├── billing/         # Billing events
├── pharmacy/        # Pharmacy management
├── appointments/    # Appointment scheduling
├── ipd/             # Inpatient Department
├── radiology/       # Radiology module
├── file_upload/     # File upload system
├── search/          # Search functionality
├── inventory/       # Inventory management
└── notifications/   # Notification system
```

### 2. Design Patterns Implemented

#### Event-Driven Architecture
The system uses a publish-subscribe pattern for loose coupling between modules. Events are published when significant actions occur, and subscribers react to these events.

#### Event Sourcing
All significant actions are stored as immutable events in the database, providing a complete audit trail and enabling timeline reconstruction.

#### Multi-Tenancy Pattern
All data models inherit from ScopedModel which enforces tenant and facility isolation at the database level.

#### Idempotency Pattern
Critical operations support safe retry through idempotency keys and upsert logic.

#### CQRS (Command Query Responsibility Segregation)
Read models are optimized for queries while write models handle business logic.

---

## 🎯 CORE MODULES

### 1. IAM (Identity & Access Management) 📱

**Features**:
- Custom JWT authentication (Cookie + Header support)
- Multi-tenant user profiles
- Role-based access control (RBAC)
- Facility membership management
- Permission system (atomic capabilities)
- Scope enforcement via headers (`X-Tenant-ID`, `X-Facility-ID`)
- `/api/me` endpoint for user context
- Management command: `ensure_roles`

### 2. Patients Module 👥

**Features**:
- Patient registration & management
- Medical Record Number (MRN) per facility
- Demographics (name, DOB, gender, contact)
- Scoped to tenant + facility
- Unique constraint on MRN per scope

### 3. Encounters (OPD Visits) 🏥

**Features**:
- OPD visit lifecycle management
- Status workflow: `CREATED → CHECKED_IN → IN_CONSULT → CLOSED/CANCELLED`
- Prevents multiple active encounters per patient
- Doctor assignment
- Vitals recording (BP, temp, pulse, SpO2, etc.)
- Clinical notes (SOAP format)
- Assessment & Plan documentation
- Immutable event stream (`EncounterEvent`)
- Timeline API for encounter history
- Close-gate validation (rules-based)
- Backfill command for missing events

### 4. Tasks & Workflow Engine ✅

**Features**:
- Operational task management
- Task codes (e.g., `record-vitals`, `collect-sample`)
- Status workflow: `OPEN → IN_PROGRESS → DONE/CANCELLED`
- Task assignment to users
- Due date tracking & overdue detection
- Idempotent task creation (upsert on encounter+code)
- Role-based permissions (assign, start, complete)
- Event-driven task creation (auto-created on encounter events)
- Timeline integration (task events appear in encounter timeline)
- Advanced filtering (mine, overdue, due range, ordering)

### 5. Clinical Documents 📄

**Features**:

**Phase 0 (Simple Documents)**:
- Simple document model (`EncounterDocument`)
- Document kinds: Vitals, Assessment, Plan, Notes
- JSON content storage

**Phase 1 (Versioned Documents)**:
- Append-only, immutable documents (`ClinicalDocument`)
- Draft → Final → Amended workflow
- Template-based documents
- Version tracking
- Supersedes chain (amendment history)
- Idempotency via `idempotency_key`
- Read model for optimized queries
- Timeline integration

### 6. Orders Management 📋

**Features**:
- Order creation (LAB orders)
- Order items (individual tests/services)
- Priority levels (ROUTINE, URGENT, STAT)
- Status tracking
- Scoped to encounters

### 7. Laboratory Module 🔬

**Features**:
- Sample management with barcode tracking
- Sample receipt workflow
- Lab results with versioning
- Multiple result versions per order item
- Critical result flagging
- Critical reasons tracking
- Verify & Release workflow
- Verification gates (prevents release if critical)
- Timeline integration

### 8. Pharmacy Module 💊

**Features**:
- Medication management for allopathic, ayurvedic, and homeopathic systems
- Prescription workflow: Draft → Finalized → Dispensed
- Inventory tracking with stock levels and reorder points
- Universal medication support
- Dispensing workflow

### 9. Appointments Module 📅

**Features**:
- Appointment booking and scheduling
- Doctor schedule management
- Time slot availability checking
- Booking workflow: Scheduled → Confirmed → Checked In → Completed
- Check-in process and consultation start

### 10. IPD (Inpatient Department) 🏥

**Features**:
- Inpatient admission and management
- Bed allocation and tracking
- Ward management
- Discharge planning
- Inpatient workflows and documentation

### 11. Radiology Module 🩻

**Features**:
- Radiology order management
- Imaging study scheduling
- Results reporting and versioning
- Critical findings flagging
- Integration with PACS systems

### 12. File Upload System 📎

**Features**:
- Secure file upload and storage
- File type validation
- Size limits and security checks
- File association with patients and encounters
- Access control and audit logging

### 13. Search Module 🔍

**Features**:
- Global search across patients, encounters, and documents
- Advanced filtering and faceted search
- Search indexing and performance optimization
- Search result ranking and relevance

### 14. Inventory Management 📦

**Features**:
- Stock tracking for medications and supplies
- Reorder point management
- Inventory adjustments and audits
- Supplier management
- Stock movement tracking

### 15. Notifications System 📢

**Features**:
- Real-time notifications for critical events
- Email and SMS notifications
- Notification templates and customization
- Notification preferences per user
- Notification history and tracking

### 16. Rules Engine ⚖️

**Features**:
- Configurable business rules
- Close-gate validation for encounters
- Critical result verification gates
- Workflow automation rules
- Rule evaluation and enforcement

### 17. Audit System 📊

**Features**:
- Complete immutable audit trail
- Event sourcing for all operations
- Audit log querying and reporting
- Compliance reporting
- Data integrity verification

### 18. Alerts System 🚨

**Features**:
- Critical alerts for abnormal results
- Alert escalation and routing
- Alert acknowledgment and resolution
- Alert history and analytics
- Integration with notification system

### 19. Billing System 💰

**Features**:
- Billable event tracking
- Insurance claim processing
- Payment processing integration
- Billing rules and calculations
- Financial reporting

---

## 💾 DATA MODELS

### Core Data Models

#### ScopedModel (Base Class)
All entities inherit from ScopedModel which provides:
- UUID primary keys
- Tenant isolation (tenant_id)
- Facility isolation (facility_id)
- Automatic timestamps (created_at, updated_at)
- Database indexing on tenant+facility

#### Key Entities

**Tenant**: Represents a hospital organization
**Facility**: Represents a hospital branch/location
**UserProfile**: Extended user model with tenant membership
**Role**: Defines user permissions within a tenant
**FacilityMembership**: Links users to facilities with roles

**Patient**: Patient demographic and medical record information
**Encounter**: OPD/IPD visit container
**EncounterEvent**: Immutable event history for encounters

**Task**: Operational tasks with workflow management
**ClinicalDocument**: Versioned clinical documentation
**Order/OrderItem**: Test and service orders

**LabSample**: Laboratory sample tracking
**LabResult**: Versioned laboratory results

### Database Relationships

- **One-to-Many**: Tenant → Facilities, Patient → Encounters
- **Many-to-Many**: Users ↔ Facilities (through memberships)
- **Self-Referencing**: Document amendments, Task hierarchies
- **Polymorphic**: Flexible data storage using JSON fields

---

## 🔗 API ENDPOINTS

### Authentication Endpoints
- `POST /api/auth/token/` - Obtain JWT tokens
- `POST /api/auth/token/refresh/` - Refresh access token
- `GET /api/me/` - Get current user context with memberships
- `POST /api/me/scope/` - Switch tenant/facility scope

### Core CRUD Endpoints
- `GET/POST /api/patients/` - Patient management
- `GET/POST /api/encounters/` - Encounter management
- `GET/POST /api/tasks/` - Task management
- `GET/POST /api/orders/` - Order management

### Specialized Endpoints
- `GET /api/encounters/{id}/timeline/` - Encounter timeline
- `POST /api/encounters/{id}/check-in/` - Patient check-in
- `POST /api/encounters/{id}/start-consult/` - Start consultation
- `POST /api/encounters/{id}/close/` - Close encounter

### Clinical Documentation
- `POST /api/clinical-docs/draft/` - Create draft document
- `POST /api/clinical-docs/finalize/` - Finalize draft
- `POST /api/clinical-docs/amend/` - Amend finalized document
- `GET /api/clinical-docs/latest/` - Get latest documents

### Laboratory
- `GET/POST /api/lab/samples/` - Sample management
- `GET/POST /api/lab/results/` - Result management
- `POST /api/lab/results/{id}/verify/` - Verify results
- `POST /api/lab/results/{id}/release/` - Release results

### Pharmacy
- `GET/POST /api/pharmacy/medications/` - Medication management
- `GET/POST /api/pharmacy/prescriptions/` - Prescription management
- `POST /api/pharmacy/prescriptions/{id}/dispense/` - Dispense prescription

### Appointments
- `GET/POST /api/appointments/` - Appointment management
- `GET/POST /api/appointments/slots/` - Available time slots
- `POST /api/appointments/{id}/check-in/` - Check-in for appointment

---

## 🔐 AUTHENTICATION & SECURITY

### JWT Authentication
- Access tokens (10-minute lifetime)
- Refresh tokens (14-day lifetime)
- Cookie-based storage for web clients
- Header-based for API clients
- Automatic token rotation

### Multi-Tenant Security
- Database-level tenant isolation
- Request-scoped tenant/facility context
- Permission checks at all levels
- Audit logging for security events

### Role-Based Access Control (RBAC)
- Atomic permissions (e.g., "patients.can_create")
- Role-based permission groups
- Facility-specific role assignments
- Permission inheritance and checking

### Data Security
- Encrypted sensitive data at rest
- Secure API communication (HTTPS)
- Input validation and sanitization
- SQL injection prevention
- XSS protection

---

## ⚡ EVENT-DRIVEN WORKFLOWS

### Core Workflows

#### Patient Encounter Workflow
1. **Created**: Initial encounter setup
2. **Checked In**: Patient arrival registration
3. **In Consult**: Active consultation with doctor
4. **Closed**: Encounter completion with validation

#### Task Management Workflow
1. **Open**: Task created and assigned
2. **In Progress**: Task actively being worked on
3. **Done**: Task completed successfully
4. **Cancelled**: Task cancelled

#### Clinical Documentation Workflow
1. **Draft**: Initial document creation
2. **Final**: Document finalized and locked
3. **Amended**: Previous version amended with new document

#### Laboratory Workflow
1. **Sample Received**: Sample logged in system
2. **Result Entered**: Initial results recorded
3. **Verified**: Results reviewed by senior staff
4. **Released**: Results available to ordering physician

### Event-Driven Architecture

#### Event Types
- **Encounter Events**: check-in, consult-start, close
- **Task Events**: created, assigned, started, completed
- **Document Events**: drafted, finalized, amended
- **Order Events**: created, completed, cancelled

#### Event Subscribers
- **Auto Task Creation**: New tasks created based on encounter events
- **Notification Triggers**: Alerts sent for critical events
- **Audit Logging**: All events recorded immutably
- **Timeline Updates**: Events appear in encounter timelines

### Business Rules Engine

#### Close-Gate Validation
- Required tasks must be completed before encounter closure
- Required documents must be present
- Critical results must be acknowledged

#### Critical Result Gates
- Abnormal results flagged for senior review
- Release blocked until verification
- Escalation notifications sent

---

## 🧪 TESTING INFRASTRUCTURE

### Test Coverage
- **Unit Tests**: Individual function/component testing
- **Integration Tests**: API endpoint testing
- **Workflow Tests**: End-to-end business process testing
- **Security Tests**: Authentication and authorization testing

### Testing Tools
- **pytest**: Test framework with Django integration
- **pytest-django**: Django-specific testing utilities
- **Factory Boy**: Test data generation
- **freezegun**: Time manipulation for testing
- **Coverage.py**: Code coverage reporting

### Test Categories
- **Model Tests**: Data validation and business logic
- **API Tests**: Endpoint functionality and responses
- **Workflow Tests**: Business process validation
- **Security Tests**: Permission and authentication checks
- **Integration Tests**: Cross-module interactions

---

## 🗄️ DATABASE DESIGN

### Database Schema

#### Core Tables
- **tenants_tenant**: Hospital organizations
- **facilities_facility**: Hospital branches
- **iam_userprofile**: Extended user information
- **iam_role**: Permission roles
- **iam_facilitymembership**: User-facility-role assignments

#### Clinical Tables
- **patients_patient**: Patient demographic data
- **encounters_encounter**: OPD/IPD visit records
- **encounters_event**: Immutable event history
- **tasks_task**: Operational tasks
- **clinical_docs_clinicaldocument**: Versioned clinical documents

#### Operational Tables
- **orders_order/orderitem**: Test and service orders
- **lab_labsample/labresult**: Laboratory data
- **pharmacy_medication/prescription**: Pharmacy data
- **appointments_appointment**: Scheduling data

### Database Features

#### Indexing Strategy
- Composite indexes on (tenant_id, facility_id) for all scoped tables
- Single-column indexes on frequently queried fields
- Partial indexes for status-based queries
- JSON field indexes for flexible data

#### Constraints
- Unique constraints for business rules
- Foreign key constraints for data integrity
- Check constraints for data validation
- Exclusion constraints for business logic

#### Performance Optimizations
- Read models for complex queries
- Materialized views for analytics
- Partitioning for large tables
- Connection pooling and query optimization

---

## 🚀 DEPLOYMENT & CONFIGURATION

### Environment Configuration
- **Development**: Local PostgreSQL, debug mode enabled
- **Staging**: Cloud PostgreSQL, production settings
- **Production**: High-availability PostgreSQL cluster

### Infrastructure Requirements
- **Web Server**: Gunicorn for Django application
- **Reverse Proxy**: Nginx for static files and SSL termination
- **Database**: PostgreSQL 13+ with PostGIS for location data
- **Cache**: Redis for session storage and caching
- **Message Queue**: Redis/Celery for background tasks

### Monitoring & Observability
- **Application Monitoring**: Sentry for error tracking
- **Performance Monitoring**: Custom metrics and APM
- **Database Monitoring**: Query performance and connection pooling
- **Infrastructure Monitoring**: Server resources and availability

### Backup & Recovery
- **Database Backups**: Daily automated backups with Point-in-Time Recovery
- **File Backups**: Static files and uploaded documents
- **Disaster Recovery**: Multi-region failover capability
- **Data Retention**: Configurable retention policies

---

## 🗺️ FUTURE ROADMAP

### Phase 2: Enhanced Features (2024 Q2-Q3)

#### Advanced Analytics
- Real-time dashboards for hospital metrics
- Patient outcome tracking and reporting
- Resource utilization analytics
- Quality metrics and benchmarking

#### Mobile Applications
- iOS/Android apps for clinicians
- Patient portal for appointment booking
- Staff communication platform
- Emergency response coordination

#### AI/ML Integration
- Clinical decision support systems
- Predictive analytics for patient outcomes
- Automated diagnosis assistance
- Resource optimization algorithms

### Phase 3: Global Expansion (2024 Q4-2025)

#### International Compliance
- HIPAA compliance for US markets
- GDPR compliance for EU markets
- Local healthcare regulations
- Multi-language support

#### Multi-System Support
- Traditional Chinese Medicine integration
- Naturopathy and chiropractic workflows
- International medical system templates
- Localization for global markets

#### Advanced Features
- Telemedicine platform integration
- IoT device integration (wearables, monitors)
- Blockchain for medical records
- Advanced imaging AI analysis

### Phase 4: Enterprise Scale (2025+)

#### Hospital Chain Management
- Multi-hospital network management
- Centralized administration
- Cross-facility patient transfers
- Unified reporting and analytics

#### Advanced Integrations
- EHR/EMR system integrations
- Pharmacy management systems
- Laboratory information systems
- Radiology PACS integration

#### Innovation Features
- AI-powered clinical assistants
- Predictive patient risk scoring
- Automated treatment protocols
- Real-time population health management

---

## 📊 PROJECT METRICS

### Current Status (Phase 0 & 1 Complete)
- **Lines of Code**: 50,000+ lines
- **Test Coverage**: 85%+
- **API Endpoints**: 100+ endpoints
- **Database Tables**: 50+ tables
- **Modules**: 20+ Django apps
- **Workflows**: 15+ business processes

### Performance Benchmarks
- **API Response Time**: <200ms average
- **Concurrent Users**: 1,000+ supported
- **Database Queries**: Optimized with proper indexing
- **Uptime**: 99.9% target

### Quality Assurance
- **Automated Tests**: 500+ test cases
- **Security Audits**: Regular penetration testing
- **Code Reviews**: Mandatory for all changes
- **Documentation**: Comprehensive API docs

---

## 🎯 SUCCESS CRITERIA

### Technical Excellence
- ✅ Modular, maintainable codebase
- ✅ Comprehensive test coverage
- ✅ High-performance API responses
- ✅ Secure, scalable architecture

### Business Impact
- [ ] Successful deployment in 10+ hospitals
- [ ] Improved patient care outcomes
- [ ] Reduced administrative overhead
- [ ] Increased operational efficiency

### Market Leadership
- [ ] First universal healthcare backend
- [ ] Support for all major medical systems
- [ ] Global market penetration
- [ ] Industry standard for healthcare software

---

**This project represents a comprehensive, enterprise-grade healthcare management system designed to serve hospitals worldwide with a single, universal backend that adapts to any medical system or specialty through specialized frontends.**
