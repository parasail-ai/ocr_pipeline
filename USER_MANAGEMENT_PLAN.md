# User Management System Implementation Plan

## Summary
Starting implementation of a lightweight user management system for the OCR Pipeline.

## Requirements
1. **Admin User**: matthew.carnali@parasail.io (password: Hqbiscuit51!) - can see all documents, manage users
2. **Test User**: test@test.com (password: test1234) - basic user
3. **Document Ownership**: Each document tagged with user_id, users only see their own documents
4. **Admin Privileges**: Admins can see all documents and manage all users

## What's Been Done

### 1. Database Models Created ✅
- **User Model** added to `app/db/models.py`:
  - id, email, password_hash, full_name
  - is_admin, is_active flags
  - created_at, updated_at, last_login_at timestamps
  
- **Document Model Updated** with user_id foreign key:
  - Links each document to the user who uploaded it
  - CASCADE delete - if user deleted, their documents are deleted

### 2. Migration Created ✅
- Migration file: `alembic/versions/46d6eb456b90_add_user_management_system.py`
- Creates users table
- Seeds two initial users (admin and test)
- Adds user_id column to documents table
- Assigns existing documents to admin user

### 3. Migration Issues ⚠️
**Current Problem**: Previous migrations have issues with existing data, preventing the new migration from running.

**Solution Needed**:
- Fix previous migrations first OR
- Create a fresh database OR
- Manually apply SQL changes

## What Still Needs To Be Done

### 1. Database Migration
- [ ] Resolve migration conflicts
- [ ] Successfully run migration to add users table
- [ ] Verify users and user_id column created

### 2. Update Authentication Service
- [ ] Modify `app/services/auth.py` to use database instead of in-memory
- [ ] Use bcrypt for password hashing (more secure than SHA256)
- [ ] Store sessions in database or Redis

### 3. Update Auth Routes
- [ ] Modify login to query database
- [ ] Update session handling
- [ ] Add user registration endpoint (admin only)

### 4. Update Document Routes
- [ ] Filter documents by user_id for regular users
- [ ] Show all documents for admins
- [ ] Add user_id when creating documents

### 5. Create User Management Endpoints
```python
# New routes needed in app/api/routes/users.py:
GET /api/users - List all users (admin only)
POST /api/users - Create new user (admin only)
PUT /api/users/{id} - Update user (admin only)
DELETE /api/users/{id} - Delete user (admin only)
PUT /api/users/{id}/admin - Toggle admin status (admin only)
```

### 6. Update Frontend
- [ ] Add login page if not authenticated
- [ ] Show current user email in header
- [ ] Add user management page for admins
- [ ] Filter document list based on permissions

### 7. Add to Upload Flow
- [ ] Capture current user_id from session
- [ ] Set user_id when creating Document record
- [ ] Update background task to handle user_id

## Quick Start Commands

### Option A: Fresh Database (Easiest)
```bash
# Drop and recreate database
psql -U postgres -c "DROP DATABASE ocr_pipeline;"
psql -U postgres -c "CREATE DATABASE ocr_pipeline;"

# Run all migrations
alembic upgrade head
```

### Option B: Manual SQL (If migrations fail)
```sql
-- Create users table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP
);

CREATE INDEX ix_users_email ON users(email);

-- Insert admin user
INSERT INTO users (id, email, password_hash, full_name, is_admin, is_active, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'matthew.carnali@parasail.io',
    encode(digest('Hqbiscuit51!', 'sha256'), 'hex'),
    'Matthew Carnali',
    TRUE,
    TRUE,
    NOW(),
    NOW()
);

-- Insert test user  
INSERT INTO users (id, email, password_hash, full_name, is_admin, is_active, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'test@test.com',
    encode(digest('test1234', 'sha256'), 'hex'),
    'Test User',
    FALSE,
    TRUE,
    NOW(),
    NOW()
);

-- Add user_id to documents
ALTER TABLE documents ADD COLUMN user_id UUID;

-- Set existing documents to admin
UPDATE documents 
SET user_id = (SELECT id FROM users WHERE email = 'matthew.carnali@parasail.io' LIMIT 1)
WHERE user_id IS NULL;

-- Make user_id NOT NULL
ALTER TABLE documents ALTER COLUMN user_id SET NOT NULL;

-- Add foreign key
ALTER TABLE documents 
ADD CONSTRAINT documents_user_id_fkey 
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX ix_documents_user_id ON documents(user_id);
```

## Security Considerations

1. **Password Hashing**: Should use bcrypt instead of SHA256
   ```bash
   pip install bcrypt
   ```

2. **Session Management**: Consider using Redis for sessions instead of in-memory dict

3. **API Keys**: Existing API key system can coexist with user system

4. **HTTPS**: Ensure cookies are secure in production

## Testing Plan

1. **Test Login**:
   - Login as admin (matthew.carnali@parasail.io / Hqbiscuit51!)
   - Login as test user (test@test.com / test1234)
   - Verify sessions work

2. **Test Document Filtering**:
   - Upload document as test user
   - Verify test user only sees their documents
   - Login as admin, verify admin sees all documents

3. **Test User Management** (admin only):
   - Create new user
   - Toggle admin status
   - Delete user
   - Verify deleted user's documents are removed

## Files Modified So Far

- `app/db/models.py` - Added User model, updated Document model
- `alembic/versions/46d6eb456b90_add_user_management_system.py` - Migration file

## Files That Need Modification

- `app/services/auth.py` - Use database queries
- `app/api/routes/auth.py` - Update login/logout logic
- `app/api/routes/documents.py` - Add user filtering
- `app/api/routes/users.py` - NEW FILE - User management endpoints
- `app/models/user.py` - NEW FILE - Pydantic models for User
- `app/api/dependencies/auth.py` - Add get_current_user dependency
- Frontend templates - Add login page, user management

## Next Steps

1. **Resolve Migration Issues**: Fix database state to allow migrations
2. **Install bcrypt**: `pip install bcrypt`
3. **Update auth service**: Query database for users
4. **Test login flow**: Verify authentication works
5. **Add user filtering**: Filter documents by user_id
6. **Build user management UI**: Admin interface for user CRUD

## Notes

- User management is separate from existing API key system
- API keys can still be used for programmatic access
- Sessions are cookie-based for web UI
- Admin users have full access, regular users only see their own documents
