def test_health_reports_db_and_redis(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body == {"status": "ok", "database": "ok", "redis": "ok"}
