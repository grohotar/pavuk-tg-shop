"""
Migration 007: Add source field to users table
"""

async def upgrade(connection):
    """Add source column to users table to track where user came from"""
    await connection.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS source VARCHAR;
    """)
    
    await connection.execute("""
        CREATE INDEX IF NOT EXISTS ix_users_source ON users(source);
    """)


async def downgrade(connection):
    """Remove source column from users table"""
    await connection.execute("""
        DROP INDEX IF EXISTS ix_users_source;
    """)
    
    await connection.execute("""
        ALTER TABLE users 
        DROP COLUMN IF EXISTS source;
    """)
