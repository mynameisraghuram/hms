# Fix test_scope_headers_block_non_member Test

## Problem
Test is failing with `assert 200 == 403` because the authentication class that enforces scope headers is being bypassed.

## Root Cause
The `api_client` fixture uses `force_authenticate()` which bypasses DRF authentication classes, so `CookieOrHeaderJWTAuthentication.authenticate()` never runs, and therefore `apply_scope_from_headers()` is never called.

## Solution
Modify the test to use a fresh APIClient instance without force_authenticate, so the real JWT authentication flow executes.

## Files Edited
- [x] backend/hm_core/iam/tests/test_auth_and_me.py - Fixed the test to not use the api_client fixture

## Changes Made
1. ✅ Removed `api_client` parameter from test function signature
2. ✅ Created fresh `APIClient()` instance inside the test
3. ✅ Set credentials with Bearer token using `client.credentials()`
4. ✅ Test now properly triggers authentication class which enforces scope validation

## How the Fix Works
- Before: `api_client` fixture used `force_authenticate()` → bypassed authentication classes → scope validation never ran → test got 200
- After: Fresh `APIClient()` with real JWT token → authentication class runs → `apply_scope_from_headers()` called → membership check fails → test gets 403 ✅

## To Verify
Run the test with (Windows Command Prompt with venv):
```cmd
cd backend
venv\Scripts\activate
pytest hm_core/iam/tests/test_auth_and_me.py::test_scope_headers_block_non_member -v
```

Or if venv is already activated:
```cmd
cd backend
pytest hm_core/iam/tests/test_auth_and_me.py::test_scope_headers_block_non_member -v
```

The test should now pass with the expected 403 status code.
