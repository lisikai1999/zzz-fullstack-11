import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_create_task(client):
    resp = await client.post(
        "/api/tasks",
        json={
            "name": "test-task",
            "cron_expression": "*/5 * * * *",
            "timezone": "UTC",
            "overlap_policy": "SKIP",
            "catchup_policy": "NONE",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-task"
    assert data["cron_expression"] == "*/5 * * * *"
    assert data["status"] == "active"
    assert data["next_fire_time"] is not None


@pytest.mark.asyncio
async def test_create_task_invalid_cron(client):
    resp = await client.post(
        "/api/tasks",
        json={
            "name": "bad-cron",
            "cron_expression": "invalid",
            "timezone": "UTC",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_task_invalid_timezone(client):
    resp = await client.post(
        "/api/tasks",
        json={
            "name": "bad-tz",
            "cron_expression": "* * * * *",
            "timezone": "Invalid/Zone",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_tasks(client):
    await client.post(
        "/api/tasks",
        json={
            "name": "list-test",
            "cron_expression": "* * * * *",
            "timezone": "UTC",
        },
    )
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_task(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "name": "get-test",
            "cron_expression": "* * * * *",
            "timezone": "UTC",
        },
    )
    task_id = create_resp.json()["id"]
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_get_task_not_found(client):
    resp = await client.get("/api/tasks/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "name": "update-test",
            "cron_expression": "* * * * *",
            "timezone": "UTC",
        },
    )
    task_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/tasks/{task_id}",
        json={"cron_expression": "0 * * * *"},
    )
    assert resp.status_code == 200
    assert resp.json()["cron_expression"] == "0 * * * *"


@pytest.mark.asyncio
async def test_delete_task(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "name": "delete-test",
            "cron_expression": "* * * * *",
            "timezone": "UTC",
        },
    )
    task_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pause_and_resume_task(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "name": "pause-test",
            "cron_expression": "* * * * *",
            "timezone": "UTC",
        },
    )
    task_id = create_resp.json()["id"]

    # Pause
    resp = await client.post(f"/api/tasks/{task_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"
    assert resp.json()["next_fire_time"] is None

    # Start
    resp = await client.post(f"/api/tasks/{task_id}/start")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    assert resp.json()["next_fire_time"] is not None


@pytest.mark.asyncio
async def test_stop_task(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "name": "stop-test",
            "cron_expression": "* * * * *",
            "timezone": "UTC",
        },
    )
    task_id = create_resp.json()["id"]

    resp = await client.post(f"/api/tasks/{task_id}/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"
    assert resp.json()["next_fire_time"] is None


@pytest.mark.asyncio
async def test_preview_fires(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "name": "preview-test",
            "cron_expression": "0 * * * *",
            "timezone": "UTC",
        },
    )
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/api/tasks/{task_id}/fires", params={"n": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["fire_times"]) == 5


@pytest.mark.asyncio
async def test_logs_endpoint(client):
    create_resp = await client.post(
        "/api/tasks",
        json={
            "name": "log-test",
            "cron_expression": "* * * * *",
            "timezone": "UTC",
        },
    )
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/api/tasks/{task_id}/logs")
    assert resp.status_code == 200

    resp = await client.get("/api/logs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
