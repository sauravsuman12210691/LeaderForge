"""
Script to populate database with 1M users and 5M game sessions.
Uses batch processing for efficiency.
"""
import sys
import os
import time
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import numpy as np

from app.config import get_settings
from app.models import Base

fake = Faker()
settings = get_settings()

# Create engine
engine = create_engine(settings.database_url, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(bind=engine)


def create_tables():
    """Create all tables."""
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")


def generate_users(session, total_users=1_000_000, batch_size=10_000):
    """Generate and insert users in batches."""
    print(f"\nGenerating {total_users:,} users...")
    start_time = time.time()
    
    for batch_start in range(0, total_users, batch_size):
        batch_end = min(batch_start + batch_size, total_users)
        batch_size_actual = batch_end - batch_start
        
        # Generate batch of users
        users_data = []
        for i in range(batch_size_actual):
            users_data.append({
                'username': f"user_{batch_start + i}_{fake.user_name()}",
                'email': f"user_{batch_start + i}@{fake.domain_name()}"
            })
        
        # Batch insert using raw SQL for performance
        insert_query = text("""
            INSERT INTO users (username, email, created_at)
            VALUES (:username, :email, NOW())
        """)
        
        session.execute(insert_query, users_data)
        session.commit()
        
        # Progress update
        elapsed = time.time() - start_time
        progress = (batch_end / total_users) * 100
        rate = batch_end / elapsed if elapsed > 0 else 0
        print(f"Progress: {progress:.1f}% ({batch_end:,}/{total_users:,}) - "
              f"{rate:.0f} users/sec - ETA: {((total_users - batch_end) / rate / 60):.1f} min")
    
    total_time = time.time() - start_time
    print(f"\n✓ Created {total_users:,} users in {total_time:.2f} seconds ({total_users/total_time:.0f} users/sec)")


def generate_game_sessions(session, total_sessions=5_000_000, batch_size=10_000):
    """Generate and insert game sessions with Zipf distribution."""
    print(f"\nGenerating {total_sessions:,} game sessions...")
    start_time = time.time()
    
    # Get total user count
    result = session.execute(text("SELECT COUNT(*) FROM users"))
    total_users = result.scalar()
    
    # Get user IDs
    result = session.execute(text("SELECT id FROM users ORDER BY id"))
    user_ids = [row[0] for row in result.fetchall()]
    
    print(f"Total users in database: {total_users:,}")
    
    # Use Zipf distribution for realistic gameplay patterns
    # Some users play much more than others
    zipf_param = 1.5  # Exponent for Zipf distribution
    
    for batch_start in range(0, total_sessions, batch_size):
        batch_end = min(batch_start + batch_size, total_sessions)
        batch_size_actual = batch_end - batch_start
        
        # Generate batch of sessions
        sessions_data = []
        for i in range(batch_size_actual):
            # Select user with Zipf distribution
            zipf_index = int(np.random.zipf(zipf_param)) - 1
            user_id = user_ids[min(zipf_index, len(user_ids) - 1)]
            
            # Random score between 100 and 10000
            score = random.randint(100, 10000)
            
            # Random game mode (70% solo, 30% team)
            game_mode = 'solo' if random.random() < 0.7 else 'team'
            
            # Random time within last 30 days
            days_ago = random.randint(0, 30)
            played_at = datetime.now() - timedelta(days=days_ago, 
                                                   hours=random.randint(0, 23),
                                                   minutes=random.randint(0, 59))
            
            sessions_data.append({
                'user_id': user_id,
                'score': score,
                'game_mode': game_mode,
                'played_at': played_at
            })
        
        # Batch insert
        insert_query = text("""
            INSERT INTO game_sessions (user_id, score, game_mode, played_at)
            VALUES (:user_id, :score, :game_mode, :played_at)
        """)
        
        session.execute(insert_query, sessions_data)
        session.commit()
        
        # Progress update
        elapsed = time.time() - start_time
        progress = (batch_end / total_sessions) * 100
        rate = batch_end / elapsed if elapsed > 0 else 0
        print(f"Progress: {progress:.1f}% ({batch_end:,}/{total_sessions:,}) - "
              f"{rate:.0f} sessions/sec - ETA: {((total_sessions - batch_end) / rate / 60):.1f} min")
    
    total_time = time.time() - start_time
    print(f"\n✓ Created {total_sessions:,} game sessions in {total_time:.2f} seconds ({total_sessions/total_time:.0f} sessions/sec)")


def populate_leaderboard(session):
    """Aggregate scores into leaderboard table."""
    print("\nPopulating leaderboard table...")
    start_time = time.time()
    
    # Clear existing leaderboard data
    session.execute(text("TRUNCATE TABLE leaderboard"))
    
    # Aggregate scores
    aggregate_query = text("""
        INSERT INTO leaderboard (user_id, username, total_score, session_count, last_updated)
        SELECT 
            gs.user_id,
            u.username,
            SUM(gs.score) as total_score,
            COUNT(*) as session_count,
            NOW() as last_updated
        FROM game_sessions gs
        JOIN users u ON gs.user_id = u.id
        GROUP BY gs.user_id, u.username
    """)
    
    session.execute(aggregate_query)
    session.commit()
    
    total_time = time.time() - start_time
    
    # Get stats
    result = session.execute(text("SELECT COUNT(*) FROM leaderboard"))
    leaderboard_count = result.scalar()
    
    print(f"✓ Populated leaderboard with {leaderboard_count:,} entries in {total_time:.2f} seconds")


def create_indexes(session):
    """Create additional indexes for performance."""
    print("\nCreating performance indexes...")
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_score ON game_sessions(user_id, score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_leaderboard_score_desc ON leaderboard(total_score DESC)",
    ]
    
    for idx_query in indexes:
        try:
            session.execute(text(idx_query))
            session.commit()
            print(f"✓ Created index")
        except Exception as e:
            print(f"✗ Index creation failed or already exists: {e}")
            session.rollback()


def print_statistics(session):
    """Print database statistics."""
    print("\n" + "="*60)
    print("DATABASE STATISTICS")
    print("="*60)
    
    # User count
    result = session.execute(text("SELECT COUNT(*) FROM users"))
    print(f"Total Users: {result.scalar():,}")
    
    # Session count
    result = session.execute(text("SELECT COUNT(*) FROM game_sessions"))
    print(f"Total Game Sessions: {result.scalar():,}")
    
    # Leaderboard count
    result = session.execute(text("SELECT COUNT(*) FROM leaderboard"))
    print(f"Leaderboard Entries: {result.scalar():,}")
    
    # Top 5 players
    result = session.execute(text("""
        SELECT username, total_score, session_count
        FROM leaderboard
        ORDER BY total_score DESC
        LIMIT 5
    """))
    
    print("\nTop 5 Players:")
    for idx, (username, score, sessions) in enumerate(result.fetchall(), 1):
        print(f"  {idx}. {username}: {score:,} points ({sessions} sessions)")
    
    # Score distribution
    result = session.execute(text("""
        SELECT 
            MIN(total_score) as min_score,
            MAX(total_score) as max_score,
            AVG(total_score)::INTEGER as avg_score,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_score)::INTEGER as median_score
        FROM leaderboard
    """))
    row = result.fetchone()
    print(f"\nScore Distribution:")
    print(f"  Min: {row[0]:,}")
    print(f"  Max: {row[1]:,}")
    print(f"  Avg: {row[2]:,}")
    print(f"  Median: {row[3]:,}")
    
    print("="*60)


def main():
    """Main execution function."""
    print("="*60)
    print("LEADERFORGE DATA POPULATION SCRIPT")
    print("="*60)
    print(f"Target: 1M users, 5M game sessions")
    print(f"Database: {settings.database_url}")
    print("="*60)
    
    overall_start = time.time()
    
    session = SessionLocal()
    
    try:
        # Step 1: Create tables
        create_tables()
        
        # Step 2: Generate users
        generate_users(session, total_users=1_000_000, batch_size=10_000)
        
        # Step 3: Generate game sessions
        generate_game_sessions(session, total_sessions=5_000_000, batch_size=10_000)
        
        # Step 4: Populate leaderboard
        populate_leaderboard(session)
        
        # Step 5: Create indexes
        create_indexes(session)
        
        # Step 6: Print statistics
        print_statistics(session)
        
        overall_time = time.time() - overall_start
        print(f"\n✓ Total execution time: {overall_time/60:.2f} minutes")
        print("✓ Data population completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error during data population: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
