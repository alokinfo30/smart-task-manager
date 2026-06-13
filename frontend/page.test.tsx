import '@testing-library/jest-dom'
import { render, screen, waitFor } from '@testing-library/react'
import ChatApp from './app/page'

// Mock react-markdown because it uses ESM-only syntax which Jest cannot parse by default
jest.mock('react-markdown', () => (props: any) => <div className="markdown-mock">{props.children}</div>);

// Mock Next.js dynamic imports so they don't break Jest
jest.mock('next/dynamic', () => () => {
  const DynamicComponent = () => <div>Mocked Component</div>;
  return DynamicComponent;
});

// Mock fetch to prevent actual network calls (like ipapi.co) during tests
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ country_code: "US", currency: "USD" }),
  })
) as jest.Mock;

describe('ChatApp Main Page', () => {
  it('renders the authentication screen on initial load', async () => {
    render(<ChatApp />)
    
    // Wait for the component to mount (bypassing the "Loading..." state) to display the app title
    const titleElement = await screen.findByText('🔐 Smart Task Manager')
    expect(titleElement).toBeInTheDocument()
  })
})