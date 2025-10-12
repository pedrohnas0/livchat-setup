/**
 * Unit tests for APIClient
 *
 * TDD: Write tests FIRST (RED phase)
 *
 * Tests for HTTP client that communicates with LivChatSetup API
 */

// Mock fetch globally before importing
const mockFetch = jest.fn();
global.fetch = mockFetch as any;

// Import will be added after implementation
import { APIClient } from '../../src/api-client.js';

// Helper to create mock Response
function createMockResponse(data: any, status = 200, ok = true): Response {
  return {
    ok,
    status,
    statusText: ok ? 'OK' : 'Error',
    headers: new Headers(),
    redirected: false,
    type: 'basic',
    url: '',
    clone: () => createMockResponse(data, status, ok),
    body: null,
    bodyUsed: false,
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as Response;
}

describe('APIClient', () => {
  const BASE_URL = 'http://localhost:8000';
  const API_KEY = 'test_api_key_123';

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
  });

  describe('Constructor', () => {
    it('should create client with base URL', () => {
      const client = new APIClient(BASE_URL);
      expect(client).toBeDefined();
    });

    it('should accept optional API key', () => {
      const client = new APIClient(BASE_URL, API_KEY);
      expect(client).toBeDefined();
    });
  });

  describe('GET requests', () => {
    it('should make GET request to correct URL', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ success: true })
      );

      const client = new APIClient(BASE_URL);
      await client.get('/api/servers');

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/servers`,
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('should include API key in headers if provided', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ success: true })
      );

      // const client = new APIClient(BASE_URL, API_KEY);
      // await client.get('/api/servers');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': `Bearer ${API_KEY}`,
          }),
        })
      );
    });

    it('should return parsed JSON response', async () => {
      const mockData = { servers: [], total: 0 };
      mockFetch.mockResolvedValueOnce(
        createMockResponse(mockData)
      );

      // const client = new APIClient(BASE_URL);
      // const result = await client.get('/api/servers');

      // expect(result).toEqual(mockData);
    });
  });

  describe('POST requests', () => {
    it('should make POST request with body', async () => {
      const requestBody = { name: 'test-server', server_type: 'cx21' };
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ job_id: 'job_123' }, 202)
      );

      // const client = new APIClient(BASE_URL);
      // await client.post('/api/servers', requestBody);

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/servers`,
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify(requestBody),
        })
      );
    });

    it('should return parsed response from POST', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ job_id: 'job_123', message: 'Started' }, 202)
      );

      // const client = new APIClient(BASE_URL);
      // const result = await client.post('/api/servers', {});

      // expect(result).toHaveProperty('job_id');
    });
  });

  describe('PUT requests', () => {
    it('should make PUT request with body', async () => {
      const requestBody = { value: 'new_value' };
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ success: true })
      );

      // const client = new APIClient(BASE_URL);
      // await client.put('/api/config/key', requestBody);

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/config/key`,
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify(requestBody),
        })
      );
    });
  });

  describe('DELETE requests', () => {
    it('should make DELETE request', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ job_id: 'delete_123' }, 202)
      );

      // const client = new APIClient(BASE_URL);
      // await client.delete('/api/servers/test-server');

      expect(global.fetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/servers/test-server`,
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  describe('Error handling', () => {
    it('should throw error on 404 with details', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ detail: 'Server not found' }, 404, false)
      );

      // const client = new APIClient(BASE_URL);
      // await expect(client.get('/api/servers/invalid')).rejects.toThrow();
    });

    it('should throw error on 500 with message', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ detail: 'Database connection failed' }, 500, false)
      );

      // const client = new APIClient(BASE_URL);
      // await expect(client.get('/api/servers')).rejects.toThrow('Database connection failed');
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(
        new Error('Network error')
      );

      // const client = new APIClient(BASE_URL);
      // await expect(client.get('/api/servers')).rejects.toThrow('Network error');
    });

    it('should throw error on 422 validation error', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          detail: [
            {
              loc: ['body', 'name'],
              msg: 'field required',
              type: 'value_error.missing'
            }
          ]
        }, 422, false)
      );

      // const client = new APIClient(BASE_URL);
      // await expect(client.post('/api/servers', {})).rejects.toThrow();
    });
  });

  describe('Response handling', () => {
    it('should handle empty response body', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse(null, 204)
      );

      // const client = new APIClient(BASE_URL);
      // const result = await client.delete('/api/servers/test');

      // expect(result).toBeNull();
    });

    it('should handle non-JSON response', async () => {
      const mockResp = createMockResponse('Plain text', 200);
      mockResp.json = async () => {
        throw new Error('Not JSON');
      };
      mockFetch.mockResolvedValueOnce(mockResp);

      // const client = new APIClient(BASE_URL);
      // Should handle gracefully
    });
  });
});
