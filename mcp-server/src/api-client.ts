/**
 * HTTP Client for LivChatSetup API
 *
 * Provides methods to communicate with the FastAPI backend
 */

/**
 * API Error with additional context for AI
 */
export class APIError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public detail: any,
    message?: string
  ) {
    super(message || `API Error ${status}: ${statusText}`);
    this.name = 'APIError';
  }
}

/**
 * HTTP Client for LivChatSetup REST API
 */
export class APIClient {
  private baseURL: string;
  private apiKey?: string;

  /**
   * Create API client
   *
   * @param baseURL - Base URL of API (e.g., http://localhost:8000)
   * @param apiKey - Optional API key for authentication
   */
  constructor(baseURL: string, apiKey?: string) {
    this.baseURL = baseURL.replace(/\/$/, ''); // Remove trailing slash
    this.apiKey = apiKey;
  }

  /**
   * Build headers for request
   */
  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    return headers;
  }

  /**
   * Make HTTP request
   */
  private async request<T = any>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    body?: any
  ): Promise<T> {
    // Add /api prefix if endpoint doesn't already have it
    const fullEndpoint = endpoint.startsWith('/api/') ? endpoint : `/api${endpoint}`;
    const url = `${this.baseURL}${fullEndpoint}`;

    const options: RequestInit = {
      method,
      headers: this.getHeaders(),
    };

    if (body && (method === 'POST' || method === 'PUT')) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, options);

      // Try to parse JSON response
      let data: any = null;
      try {
        data = await response.json();
      } catch (err) {
        // Response might not be JSON (e.g., 204 No Content)
        if (response.status !== 204) {
          // Only warn if it's not a 204
          console.error('Failed to parse JSON response:', err);
        }
      }

      // Check if response is OK
      if (!response.ok) {
        // Extract error message from response
        let errorMessage = response.statusText;
        if (data && typeof data === 'object') {
          if (data.detail) {
            if (typeof data.detail === 'string') {
              errorMessage = data.detail;
            } else if (Array.isArray(data.detail)) {
              // Pydantic validation error
              errorMessage = data.detail.map((err: any) =>
                `${err.loc.join('.')}: ${err.msg}`
              ).join(', ');
            }
          } else if (data.message) {
            errorMessage = data.message;
          }
        }

        throw new APIError(
          response.status,
          response.statusText,
          data,
          errorMessage
        );
      }

      return data as T;
    } catch (error) {
      // Re-throw APIError as-is
      if (error instanceof APIError) {
        throw error;
      }

      // Wrap other errors (network errors, etc)
      throw new Error(
        `Network error: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  /**
   * GET request
   */
  async get<T = any>(endpoint: string): Promise<T> {
    return this.request<T>('GET', endpoint);
  }

  /**
   * POST request
   */
  async post<T = any>(endpoint: string, body: any): Promise<T> {
    return this.request<T>('POST', endpoint, body);
  }

  /**
   * PUT request
   */
  async put<T = any>(endpoint: string, body: any): Promise<T> {
    return this.request<T>('PUT', endpoint, body);
  }

  /**
   * DELETE request
   */
  async delete<T = any>(endpoint: string): Promise<T> {
    return this.request<T>('DELETE', endpoint);
  }
}
