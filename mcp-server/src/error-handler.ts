/**
 * Error Handler for MCP Server
 *
 * Formats errors for AI consumption with context and recovery suggestions
 */

import { APIError } from './api-client.js';

/**
 * Formatted error with AI-friendly context
 */
export interface FormattedError {
  type: 'api_error' | 'validation_error' | 'network_error' | 'unknown_error';
  message: string;
  status?: number;
  aiContext: string;
  suggestions: string[];
  validationErrors?: string[];
  originalError?: any;
}

/**
 * Error Handler - Static utility class
 */
export class ErrorHandler {
  /**
   * Format any error for AI consumption
   */
  static formatError(error: unknown): FormattedError {
    // Handle APIError instances
    if (error instanceof APIError) {
      return this.formatAPIError(error);
    }

    // Handle Error instances
    if (error instanceof Error) {
      return this.formatGenericError(error);
    }

    // Handle string errors
    if (typeof error === 'string') {
      return {
        type: 'unknown_error',
        message: error,
        aiContext: 'An unexpected error occurred.',
        suggestions: ['Check the error message and try again.'],
      };
    }

    // Unknown error type
    return {
      type: 'unknown_error',
      message: String(error),
      aiContext: 'An unexpected error occurred.',
      suggestions: ['Check the error details and try again.'],
      originalError: error,
    };
  }

  /**
   * Format APIError with specific handling for different status codes
   */
  private static formatAPIError(error: APIError): FormattedError {
    const status = error.status;

    // Handle validation errors (422)
    if (status === 422) {
      return this.formatValidationError(error);
    }

    // Handle other status codes
    const formatted: FormattedError = {
      type: 'api_error',
      message: error.message,
      status: error.status,
      aiContext: this.getAPIErrorContext(status),
      suggestions: this.getAPIErrorSuggestions(status),
      originalError: error.detail,
    };

    return formatted;
  }

  /**
   * Format validation error (422)
   */
  private static formatValidationError(error: APIError): FormattedError {
    const validationErrors: string[] = [];

    // Extract validation errors from detail
    if (error.detail && Array.isArray(error.detail)) {
      for (const err of error.detail) {
        const location = err.loc ? err.loc.join('.') : 'unknown';
        const message = err.msg || 'validation error';
        validationErrors.push(`${location}: ${message}`);
      }
    }

    return {
      type: 'validation_error',
      message: error.message,
      status: 422,
      aiContext: 'The request data failed validation. Please check the required fields and data types.',
      suggestions: ['Correct the input parameters and try again.'],
      validationErrors,
      originalError: error.detail,
    };
  }

  /**
   * Format generic Error
   */
  private static formatGenericError(error: Error): FormattedError {
    // Check if it's a network error
    if (error.message.includes('Network error') ||
        error.message.includes('ECONNREFUSED') ||
        error.message.includes('fetch failed')) {
      return {
        type: 'network_error',
        message: error.message,
        aiContext: 'Failed to connect to the LivChatSetup API server. The server might be offline or unreachable.',
        suggestions: [
          'Check that the API server is running (try: curl $LIVCHAT_API_URL/health)',
          'Verify the LIVCHAT_API_URL environment variable is correct',
          'Check your network connection',
        ],
      };
    }

    // Generic error
    return {
      type: 'unknown_error',
      message: error.message,
      aiContext: 'An unexpected error occurred while processing the request.',
      suggestions: ['Check the error message for details.'],
    };
  }

  /**
   * Get AI-friendly context for API error status codes
   */
  private static getAPIErrorContext(status: number): string {
    switch (status) {
      case 400:
        return 'Bad request. The request data is invalid or malformed.';
      case 401:
        return 'Authentication failed. The API key is missing or invalid.';
      case 403:
        return 'Access forbidden. You do not have permission to perform this action.';
      case 404:
        return 'Resource not found. The requested server, app, or resource does not exist.';
      case 409:
        return 'Conflict. The resource already exists or there is a conflict with the current state.';
      case 500:
        return 'Internal server error. Something went wrong on the API server.';
      case 503:
        return 'Service unavailable. The API server is temporarily unavailable.';
      default:
        if (status >= 500) {
          return 'Server error. The API encountered an unexpected problem.';
        }
        if (status >= 400) {
          return 'Client error. There is an issue with the request.';
        }
        return 'An error occurred while processing the request.';
    }
  }

  /**
   * Get recovery suggestions for API error status codes
   */
  private static getAPIErrorSuggestions(status: number): string[] {
    switch (status) {
      case 401:
        return [
          'Set the LIVCHAT_API_KEY environment variable',
          'Verify the API key is correct',
        ];
      case 404:
        return [
          'Use list-servers or list-apps to see available resources',
          'Check that the resource ID or name is correct',
        ];
      case 409:
        return [
          'Use a different name or identifier',
          'Check existing resources to avoid conflicts',
        ];
      case 500:
      case 503:
        return [
          'Check the API server logs for details',
          'Wait a moment and try again',
        ];
      default:
        return ['Check the error message and adjust your request accordingly.'];
    }
  }

  /**
   * Format error for MCP tool response
   *
   * Returns a formatted string suitable for returning from MCP tools
   */
  static formatForMCP(error: unknown): string {
    const formatted = this.formatError(error);

    let message = `❌ Error: ${formatted.message}\n\n`;
    message += `Type: ${formatted.type}\n`;

    if (formatted.status) {
      message += `Status: ${formatted.status}\n`;
    }

    message += `\nAI Context:\n${formatted.aiContext}\n`;

    if (formatted.validationErrors && formatted.validationErrors.length > 0) {
      message += `\nValidation Errors:\n`;
      for (const err of formatted.validationErrors) {
        message += `  - ${err}\n`;
      }
    }

    message += `\nSuggestions:\n`;
    for (const suggestion of formatted.suggestions) {
      message += `  - ${suggestion}\n`;
    }

    return message;
  }

  /**
   * Check if an error is retryable
   */
  static isRetryable(error: unknown): boolean {
    if (error instanceof APIError) {
      // 5xx errors are retryable
      return error.status >= 500 && error.status < 600;
    }

    if (error instanceof Error) {
      // Network errors are retryable
      if (error.message.includes('Network error') ||
          error.message.includes('ECONNREFUSED') ||
          error.message.includes('ETIMEDOUT') ||
          error.message.includes('fetch failed')) {
        return true;
      }
    }

    return false;
  }

  /**
   * Get recovery action for an error
   */
  static getRecoveryAction(error: unknown): string {
    if (error instanceof APIError) {
      switch (error.status) {
        case 401:
          return 'Set LIVCHAT_API_KEY environment variable with a valid API key';
        case 404:
          return 'Use list-servers or list-apps to find the correct resource';
        case 409:
          return 'Use a different name to avoid conflicts';
        case 422:
          return 'Correct the input parameters according to the validation errors';
        case 500:
        case 503:
          return 'Wait a moment and retry the operation';
        default:
          return 'Check the error message and adjust your request';
      }
    }

    if (error instanceof Error && error.message.includes('Network error')) {
      return 'Check API server is running and LIVCHAT_API_URL is correct';
    }

    return 'Review the error details and try again';
  }
}
