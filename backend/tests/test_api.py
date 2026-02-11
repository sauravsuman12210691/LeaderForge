"""
Unit and integration tests for LeaderForge API.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import User, GameSession, Leaderboard

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create and tear down test database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db():
    """Get test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_users(test_db):
    """Create sample users for testing."""
    users = [
        User(id=1, username="player1", email="player1@test.com"),
        User(id=2, username="player2", email="player2@test.com"),
        User(id=3, username="player3", email="player3@test.com"),
    ]
    test_db.add_all(users)
    test_db.commit()
    return users


@pytest.fixture
def sample_leaderboard(test_db, sample_users):
    """Create sample leaderboard entries."""
    entries = [
        Leaderboard(user_id=1, username="player1", total_score=5000, session_count=10),
        Leaderboard(user_id=2, username="player2", total_score=3000, session_count=5),
        Leaderboard(user_id=3, username="player3", total_score=1000, session_count=2),
    ]
    test_db.add_all(entries)
    test_db.commit()
    return entries


# ============================================================================
# Health Check Tests
# ============================================================================

def test_root_endpoint():
    """Test root endpoint returns welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    assert "LeaderForge" in response.json()["message"]


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data


# ============================================================================
# Submit Score Tests
# ============================================================================

def test_submit_score_success(sample_users):
    """Test successful score submission."""
    response = client.post(
        "/api/scores",
        json={"user_id": 1, "score": 500}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user_id"] == 1
    assert data["new_total_score"] >= 500


def test_submit_score_creates_leaderboard_entry(sample_users):
    """Test that submitting score creates leaderboard entry."""
    response = client.post(
        "/api/scores",
        json={"user_id": 1, "score": 1000}
    )
    assert response.status_code == 200
    
    # Verify leaderboard entry was created
    rank_response = client.get("/api/leaderboard/rank/1")
    assert rank_response.status_code == 200
    rank_data = rank_response.json()
    assert rank_data["total_score"] >= 1000


def test_submit_score_invalid_user():
    """Test score submission with non-existent user."""
    response = client.post(
        "/api/scores",
        json={"user_id": 999999, "score": 500}
    )
    assert response.status_code == 404


def test_submit_score_negative_score(sample_users):
    """Test score submission with negative score."""
    response = client.post(
        "/api/scores",
        json={"user_id": 1, "score": -100}
    )
    assert response.status_code == 422  # Validation error


def test_submit_score_zero_score(sample_users):
    """Test score submission with zero score."""
    response = client.post(
        "/api/scores",
        json={"user_id": 1, "score": 0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_submit_score_very_large_score(sample_users):
    """Test score submission with very large score."""
    response = client.post(
        "/api/scores",
        json={"user_id": 1, "score": 2000000}
    )
    assert response.status_code == 422  # Should exceed validation limit


def test_submit_score_missing_fields():
    """Test score submission with missing required fields."""
    response = client.post("/api/scores", json={"user_id": 1})
    assert response.status_code == 422
    
    response = client.post("/api/scores", json={"score": 500})
    assert response.status_code == 422


def test_submit_multiple_scores_same_user(sample_users):
    """Test submitting multiple scores for same user."""
    # Submit first score
    response1 = client.post(
        "/api/scores",
        json={"user_id": 1, "score": 500}
    )
    assert response1.status_code == 200
    score1 = response1.json()["new_total_score"]
    
    # Submit second score
    response2 = client.post(
        "/api/scores",
        json={"user_id": 1, "score": 300}
    )
    assert response2.status_code == 200
    score2 = response2.json()["new_total_score"]
    
    # Total should be cumulative
    assert score2 == score1 + 300


# ============================================================================
# Top Players Tests
# ============================================================================

def test_get_top_players_empty():
    """Test getting top players when leaderboard is empty."""
    response = client.get("/api/leaderboard/top")
    assert response.status_code == 200
    data = response.json()
    assert data["top_players"] == []
    assert data["total_players"] == 0


def test_get_top_players(sample_leaderboard):
    """Test getting top players."""
    response = client.get("/api/leaderboard/top?limit=10")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["top_players"]) == 3
    assert data["total_players"] == 3
    
    # Verify sorting (highest score first)
    players = data["top_players"]
    assert players[0]["username"] == "player1"
    assert players[0]["total_score"] == 5000
    assert players[0]["rank"] == 1
    
    assert players[1]["username"] == "player2"
    assert players[1]["rank"] == 2
    
    assert players[2]["username"] == "player3"
    assert players[2]["rank"] == 3


def test_get_top_players_with_limit(sample_leaderboard):
    """Test getting top players with custom limit."""
    response = client.get("/api/leaderboard/top?limit=2")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["top_players"]) == 2
    assert data["top_players"][0]["rank"] == 1
    assert data["top_players"][1]["rank"] == 2


def test_get_top_players_limit_validation():
    """Test limit parameter validation."""
    # Limit too low
    response = client.get("/api/leaderboard/top?limit=0")
    assert response.status_code == 422
    
    # Limit too high
    response = client.get("/api/leaderboard/top?limit=1000")
    assert response.status_code == 422


def test_get_top_players_has_timestamp(sample_leaderboard):
    """Test that response includes timestamp."""
    response = client.get("/api/leaderboard/top")
    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data


# ============================================================================
# Player Rank Tests
# ============================================================================

def test_get_player_rank(sample_leaderboard):
    """Test getting player rank."""
    response = client.get("/api/leaderboard/rank/1")
    assert response.status_code == 200
    data = response.json()
    
    assert data["user_id"] == 1
    assert data["username"] == "player1"
    assert data["rank"] == 1
    assert data["total_score"] == 5000
    assert data["session_count"] == 10
    assert "percentile" in data


def test_get_player_rank_middle_player(sample_leaderboard):
    """Test getting rank for middle player."""
    response = client.get("/api/leaderboard/rank/2")
    assert response.status_code == 200
    data = response.json()
    
    assert data["rank"] == 2
    assert data["total_score"] == 3000


def test_get_player_rank_last_player(sample_leaderboard):
    """Test getting rank for last player."""
    response = client.get("/api/leaderboard/rank/3")
    assert response.status_code == 200
    data = response.json()
    
    assert data["rank"] == 3
    assert data["total_score"] == 1000


def test_get_player_rank_not_found():
    """Test getting rank for non-existent player."""
    response = client.get("/api/leaderboard/rank/999999")
    assert response.status_code == 404


def test_get_player_rank_percentile_calculation(sample_leaderboard):
    """Test percentile calculation."""
    response = client.get("/api/leaderboard/rank/3")
    assert response.status_code == 200
    data = response.json()
    
    # Player 3 is rank 3 out of 3, should be in bottom percentile
    assert data["percentile"] >= 0
    assert data["percentile"] <= 100


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_game_flow(sample_users):
    """Test complete flow: submit score -> check top players -> check rank."""
    # Submit scores for multiple users
    scores = [
        (1, 1000),
        (2, 1500),
        (3, 500),
        (1, 2000),  # User 1 plays again
    ]
    
    for user_id, score in scores:
        response = client.post(
            "/api/scores",
            json={"user_id": user_id, "score": score}
        )
        assert response.status_code == 200
    
    # Check top players
    response = client.get("/api/leaderboard/top")
    assert response.status_code == 200
    top_players = response.json()["top_players"]
    
    # User 1 should be first (1000 + 2000 = 3000)
    # User 2 should be second (1500)
    # User 3 should be third (500)
    assert top_players[0]["user_id"] == 1
    assert top_players[0]["total_score"] == 3000
    assert top_players[1]["user_id"] == 2
    assert top_players[1]["total_score"] == 1500
    
    # Check individual rank
    response = client.get("/api/leaderboard/rank/1")
    assert response.status_code == 200
    rank_data = response.json()
    assert rank_data["rank"] == 1
    assert rank_data["total_score"] == 3000
    assert rank_data["session_count"] == 2


def test_concurrent_score_submissions(sample_users):
    """Test handling of concurrent score submissions."""
    # Submit multiple scores rapidly
    responses = []
    for i in range(10):
        response = client.post(
            "/api/scores",
            json={"user_id": 1, "score": 100}
        )
        responses.append(response)
    
    # All should succeed
    for response in responses:
        assert response.status_code == 200
    
    # Final score should be 100 * 10 = 1000
    rank_response = client.get("/api/leaderboard/rank/1")
    assert rank_response.status_code == 200
    assert rank_response.json()["total_score"] == 1000
    assert rank_response.json()["session_count"] == 10


# ============================================================================
# Edge Cases
# ============================================================================

def test_invalid_user_id_format():
    """Test invalid user ID formats."""
    response = client.post(
        "/api/scores",
        json={"user_id": "invalid", "score": 500}
    )
    assert response.status_code == 422
    
    response = client.get("/api/leaderboard/rank/invalid")
    assert response.status_code == 422


def test_api_with_special_characters_in_parameters():
    """Test API handles special characters properly."""
    response = client.get("/api/leaderboard/rank/1'; DROP TABLE users; --")
    assert response.status_code == 422  # Should fail validation, not SQL injection


def test_large_limit_value():
    """Test that large limit values are rejected."""
    response = client.get("/api/leaderboard/top?limit=1000000")
    assert response.status_code == 422


# ============================================================================
# Performance Tests (Basic)
# ============================================================================

def test_api_response_time_submit_score(sample_users):
    """Test that score submission is reasonably fast."""
    import time
    
    start = time.time()
    response = client.post(
        "/api/scores",
        json={"user_id": 1, "score": 500}
    )
    elapsed = (time.time() - start) * 1000  # Convert to ms
    
    assert response.status_code == 200
    # Should complete in under 1 second for local test
    assert elapsed < 1000


def test_api_response_time_get_top_players(sample_leaderboard):
    """Test that getting top players is fast."""
    import time
    
    start = time.time()
    response = client.get("/api/leaderboard/top")
    elapsed = (time.time() - start) * 1000
    
    assert response.status_code == 200
    # Should complete in under 500ms for local test
    assert elapsed < 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
