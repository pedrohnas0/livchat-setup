/**
 * Tests for Error Handler
 *
 * Following TDD: Write tests first, then implement
 */

import { describe, it, expect } from '@jest/globals';
import { ErrorHandler, FormattedError } from '../../src/error-handler.js';
import { APIError } from '../../src/api-client.js';

describe('ErrorHandler', () => {
  describe('formatError', () => {
    it('should format APIError with 404 status', () => {
      const error = new APIError(404, 'Not Found', null, 'Server not found');
      const formatted = ErrorHandler.formatError(error);

      expect(formatted.type).toBe('api_error');
      expect(formatted.status).toBe(404);
      expect(formatted.message).toBe('Server not found');
      expect(formatted.aiContext).toContain('not found');
      expect(formatted.suggestions).toHaveLength(1);
      expect(formatted.suggestions[0]).toContain('list-servers');
    });

    it('should format APIError with 401 unauthorized', () => {
      const error = new APIError(401, 'Unauthorized', null, 'Invalid API key');
      const formatted = ErrorHandler.formatError(error);

      expect(formatted.type).toBe('api_error');
      expect(formatted.status).toBe(401);
      expect(formatted.message).toBe('Invalid API key');
      expect(formatted.suggestions[0]).toContain('LIVCHAT_API_KEY');
    });

    it('should format APIError with 422 validation error', () => {
      const validationDetail = [
        { loc: ['body', 'name'], msg: 'field required' },
        { loc: ['body', 'provider'], msg: 'invalid value' }
      ];
      const error = new APIError(
        422,
        'Unprocessable Entity',
        { detail: validationDetail },
        'Validation error'
      );
      const formatted = ErrorHandler.formatError(error);

      expect(formatted.type).toBe('validation_error');
      expect(formatted.status).toBe(422);
      expect(formatted.validationErrors).toHaveLength(2);
      expect(formatted.validationErrors![0]).toContain('body.name');
      expect(formatted.suggestions[0]).toContain('correct');
    });

    it('should format APIError with 500 internal server error', () => {
      const error = new APIError(
        500,
        'Internal Server Error',
        { detail: 'Database connection failed' },
        'Server error'
      );
      const formatted = ErrorHandler.formatError(error);

      expect(formatted.type).toBe('api_error');
      expect(formatted.status).toBe(500);
      expect(formatted.suggestions[0]).toContain('API server');
    });

    it('should format APIError with 409 conflict', () => {
      const error = new APIError(
        409,
        'Conflict',
        { detail: 'Server name already exists' },
        'Conflict error'
      );
      const formatted = ErrorHandler.formatError(error);

      expect(formatted.type).toBe('api_error');
      expect(formatted.status).toBe(409);
      expect(formatted.suggestions[0]).toContain('different name');
    });

    it('should format network error', () => {
      const error = new Error('Network error: ECONNREFUSED');
      const formatted = ErrorHandler.formatError(error);

      expect(formatted.type).toBe('network_error');
      expect(formatted.message).toContain('ECONNREFUSED');
      expect(formatted.suggestions[0]).toContain('API server is running');
      expect(formatted.suggestions[1]).toContain('LIVCHAT_API_URL');
    });

    it('should format generic error', () => {
      const error = new Error('Something went wrong');
      const formatted = ErrorHandler.formatError(error);

      expect(formatted.type).toBe('unknown_error');
      expect(formatted.message).toBe('Something went wrong');
      expect(formatted.suggestions).toHaveLength(1);
    });

    it('should format string error', () => {
      const formatted = ErrorHandler.formatError('Simple error message');

      expect(formatted.type).toBe('unknown_error');
      expect(formatted.message).toBe('Simple error message');
    });
  });

  describe('formatForMCP', () => {
    it('should format error for MCP tool response', () => {
      const error = new APIError(404, 'Not Found', null, 'Server not found');
      const mcpMessage = ErrorHandler.formatForMCP(error);

      expect(mcpMessage).toContain('Error: Server not found');
      expect(mcpMessage).toContain('Type: api_error');
      expect(mcpMessage).toContain('Status: 404');
      expect(mcpMessage).toContain('AI Context:');
      expect(mcpMessage).toContain('Suggestions:');
      expect(mcpMessage).toContain('list-servers');
    });

    it('should format validation error for MCP', () => {
      const validationDetail = [
        { loc: ['body', 'name'], msg: 'field required' }
      ];
      const error = new APIError(
        422,
        'Unprocessable Entity',
        { detail: validationDetail },
        'Validation error'
      );
      const mcpMessage = ErrorHandler.formatForMCP(error);

      expect(mcpMessage).toContain('Validation Errors:');
      expect(mcpMessage).toContain('body.name: field required');
    });

    it('should format network error for MCP', () => {
      const error = new Error('Network error: Connection refused');
      const mcpMessage = ErrorHandler.formatForMCP(error);

      expect(mcpMessage).toContain('Error: Network error: Connection refused');
      expect(mcpMessage).toContain('Type: network_error');
      expect(mcpMessage).toContain('Suggestions:');
    });
  });

  describe('isRetryable', () => {
    it('should identify retryable errors (5xx)', () => {
      const error = new APIError(500, 'Internal Server Error', null);
      expect(ErrorHandler.isRetryable(error)).toBe(true);
    });

    it('should identify retryable errors (503)', () => {
      const error = new APIError(503, 'Service Unavailable', null);
      expect(ErrorHandler.isRetryable(error)).toBe(true);
    });

    it('should identify non-retryable errors (4xx)', () => {
      const error = new APIError(400, 'Bad Request', null);
      expect(ErrorHandler.isRetryable(error)).toBe(false);
    });

    it('should identify retryable network errors', () => {
      const error = new Error('Network error: ECONNREFUSED');
      expect(ErrorHandler.isRetryable(error)).toBe(true);
    });

    it('should identify non-retryable generic errors', () => {
      const error = new Error('Something wrong');
      expect(ErrorHandler.isRetryable(error)).toBe(false);
    });
  });

  describe('getRecoveryAction', () => {
    it('should suggest recovery for 401 error', () => {
      const error = new APIError(401, 'Unauthorized', null);
      const action = ErrorHandler.getRecoveryAction(error);

      expect(action).toContain('Set LIVCHAT_API_KEY');
    });

    it('should suggest recovery for 404 error', () => {
      const error = new APIError(404, 'Not Found', null);
      const action = ErrorHandler.getRecoveryAction(error);

      expect(action).toContain('list');
    });

    it('should suggest recovery for network error', () => {
      const error = new Error('Network error: ECONNREFUSED');
      const action = ErrorHandler.getRecoveryAction(error);

      expect(action).toContain('Check API server');
    });

    it('should suggest recovery for validation error', () => {
      const error = new APIError(422, 'Unprocessable Entity', null);
      const action = ErrorHandler.getRecoveryAction(error);

      expect(action).toContain('Correct the input');
    });
  });
});
