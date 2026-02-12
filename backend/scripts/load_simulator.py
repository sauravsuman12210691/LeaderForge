"""
Load simulation script to test API performance.
Simulates concurrent users making API requests.
"""
import asyncio
import aiohttp
import time
import random
import statistics
from datetime import datetime
from collections import defaultdict
import sys


class LoadSimulator:
    """Load simulator for API testing."""
    
    def __init__(self, base_url: str, concurrent_users: int, duration_seconds: int):
        self.base_url = base_url
        self.concurrent_users = concurrent_users
        self.duration_seconds = duration_seconds
        self.results = defaultdict(list)
        self.errors = defaultdict(int)
        self.total_requests = 0
        self.start_time = None
        
    async def submit_score(self, session: aiohttp.ClientSession, user_id: int):
        """Submit a random score for a user."""
        url = f"{self.base_url}/api/leaderboard/submit"
        payload = {
            "user_id": user_id,
            "score": random.randint(100, 10000)
        }
        
        start = time.time()
        try:
            async with session.post(url, json=payload) as response:
                latency = (time.time() - start) * 1000  # Convert to ms
                self.results['submit_score'].append(latency)
                self.total_requests += 1
                
                if response.status != 200:
                    self.errors['submit_score'] += 1
                    
        except Exception as e:
            self.errors['submit_score'] += 1
            print(f"Error submitting score: {e}")
    
    async def get_top_players(self, session: aiohttp.ClientSession):
        """Get top 10 players."""
        url = f"{self.base_url}/api/leaderboard/top?limit=10"
        
        start = time.time()
        try:
            async with session.get(url) as response:
                latency = (time.time() - start) * 1000
                self.results['get_top_players'].append(latency)
                self.total_requests += 1
                
                if response.status != 200:
                    self.errors['get_top_players'] += 1
                    
        except Exception as e:
            self.errors['get_top_players'] += 1
            print(f"Error getting top players: {e}")
    
    async def get_player_rank(self, session: aiohttp.ClientSession, user_id: int):
        """Get rank for a specific player."""
        url = f"{self.base_url}/api/leaderboard/rank/{user_id}"
        
        start = time.time()
        try:
            async with session.get(url) as response:
                latency = (time.time() - start) * 1000
                self.results['get_player_rank'].append(latency)
                self.total_requests += 1
                
                if response.status != 200 and response.status != 404:
                    self.errors['get_player_rank'] += 1
                    
        except Exception as e:
            self.errors['get_player_rank'] += 1
            print(f"Error getting player rank: {e}")
    
    async def user_session(self, session: aiohttp.ClientSession, user_id: int):
        """Simulate a single user's behavior."""
        end_time = self.start_time + self.duration_seconds
        
        while time.time() < end_time:
            # Random operation based on distribution
            rand = random.random()
            
            if rand < 0.70:  # 70% score submissions
                await self.submit_score(session, user_id)
            elif rand < 0.90:  # 20% top players queries
                await self.get_top_players(session)
            else:  # 10% player rank lookups
                await self.get_player_rank(session, user_id)
            
            # Random delay between requests (100-500ms)
            await asyncio.sleep(random.uniform(0.1, 0.5))
    
    async def run(self):
        """Run the load simulation."""
        print("="*60)
        print("LEADERFORGE LOAD SIMULATOR")
        print("="*60)
        print(f"Base URL: {self.base_url}")
        print(f"Concurrent Users: {self.concurrent_users}")
        print(f"Duration: {self.duration_seconds} seconds")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        self.start_time = time.time()
        
        # Create session with connection pooling
        connector = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Generate random user IDs (assuming 1M users)
            user_ids = [random.randint(1, 1_000_000) for _ in range(self.concurrent_users)]
            
            # Run concurrent user sessions
            tasks = [self.user_session(session, user_id) for user_id in user_ids]
            await asyncio.gather(*tasks)
        
        self.print_results()
    
    def calculate_percentile(self, data, percentile):
        """Calculate percentile from data."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def print_results(self):
        """Print simulation results."""
        total_duration = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("SIMULATION RESULTS")
        print("="*60)
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Total Requests: {self.total_requests:,}")
        print(f"Requests/Second: {self.total_requests / total_duration:.2f}")
        print(f"Total Errors: {sum(self.errors.values())}")
        print("="*60)
        
        # Print stats for each endpoint
        for endpoint, latencies in self.results.items():
            if not latencies:
                continue
            
            print(f"\n{endpoint.upper().replace('_', ' ')}")
            print("-" * 40)
            print(f"  Total Requests: {len(latencies):,}")
            print(f"  Errors: {self.errors.get(endpoint, 0)}")
            print(f"  Min Latency: {min(latencies):.2f} ms")
            print(f"  Max Latency: {max(latencies):.2f} ms")
            print(f"  Avg Latency: {statistics.mean(latencies):.2f} ms")
            print(f"  Median (p50): {self.calculate_percentile(latencies, 50):.2f} ms")
            print(f"  p95 Latency: {self.calculate_percentile(latencies, 95):.2f} ms")
            print(f"  p99 Latency: {self.calculate_percentile(latencies, 99):.2f} ms")
        
        print("\n" + "="*60)
        
        # Performance assessment
        avg_latencies = {
            endpoint: statistics.mean(latencies) 
            for endpoint, latencies in self.results.items()
        }
        
        print("\nPERFORMANCE ASSESSMENT")
        print("-" * 40)
        
        submit_p95 = self.calculate_percentile(self.results.get('submit_score', [0]), 95)
        top_p95 = self.calculate_percentile(self.results.get('get_top_players', [0]), 95)
        rank_p95 = self.calculate_percentile(self.results.get('get_player_rank', [0]), 95)
        
        targets = {
            'submit_score': (submit_p95, 50, "Submit Score p95"),
            'get_top_players': (top_p95, 100, "Top Players p95"),
            'get_player_rank': (rank_p95, 50, "Player Rank p95")
        }
        
        for key, (actual, target, name) in targets.items():
            status = "✓ PASS" if actual <= target else "✗ FAIL"
            print(f"  {name}: {actual:.2f}ms (target: <{target}ms) {status}")
        
        throughput = self.total_requests / total_duration
        throughput_status = "✓ PASS" if throughput >= 100 else "✗ FAIL"
        print(f"  Throughput: {throughput:.2f} req/s (target: >100 req/s) {throughput_status}")
        
        error_rate = (sum(self.errors.values()) / self.total_requests * 100) if self.total_requests > 0 else 0
        error_status = "✓ PASS" if error_rate < 1 else "✗ FAIL"
        print(f"  Error Rate: {error_rate:.2f}% (target: <1%) {error_status}")
        
        print("="*60)


async def main():
    """Main function."""
    # Configuration
    base_url = "http://localhost:8000"
    concurrent_users = 100
    duration_seconds = 60
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    if len(sys.argv) > 2:
        concurrent_users = int(sys.argv[2])
    if len(sys.argv) > 3:
        duration_seconds = int(sys.argv[3])
    
    # Run simulation
    simulator = LoadSimulator(base_url, concurrent_users, duration_seconds)
    await simulator.run()


if __name__ == "__main__":
    asyncio.run(main())
