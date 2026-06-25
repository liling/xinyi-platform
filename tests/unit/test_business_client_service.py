from unittest.mock import AsyncMock, MagicMock


async def test_verify_redirect_uri_matches_relative_path():
    """verify_redirect_uri should construct full URL from base_url + relative path."""
    from xinyi_platform.services.business_client_service import BusinessClientService

    mock_client = MagicMock()
    mock_client.base_url = "http://hm:8001/hindsight"
    mock_client.redirect_uris = ["/auth/callback"]
    mock_client.status = MagicMock()
    mock_client.status.value = "active"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_client

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Full URL from OAuth request should match base_url + relative path
    result = await BusinessClientService.verify_redirect_uri(
        mock_session, "hm-prod", "http://hm:8001/hindsight/auth/callback"
    )
    assert result is True

    # Wrong URL should not match
    result = await BusinessClientService.verify_redirect_uri(
        mock_session, "hm-prod", "http://evil.com/callback"
    )
    assert result is False
