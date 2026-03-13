export const metadata = {
  title: 'Privacy Policy - Operative1',
  description: 'Privacy policy for Operative1 social media automation platform',
}

export default function PrivacyPage() {
  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '40px 20px', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
      <h1 style={{ fontSize: '32px', fontWeight: 600, marginBottom: '8px' }}>Privacy Policy</h1>
      <p style={{ color: '#666', marginBottom: '32px' }}>Last updated: March 2025</p>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Overview</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          Operative1 ("we", "our", or "us") provides a social media automation platform that helps businesses
          engage with potential customers on Twitter/X. This privacy policy explains how we collect, use, and
          protect your information when you use our web application and Chrome extension.
        </p>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Information We Collect</h2>

        <h3 style={{ fontSize: '16px', fontWeight: 600, marginTop: '16px', marginBottom: '8px' }}>Account Information</h3>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          When you sign up, we collect your email address and authentication credentials through our
          authentication provider (Supabase). We use this to create and manage your account.
        </p>

        <h3 style={{ fontSize: '16px', fontWeight: 600, marginTop: '16px', marginBottom: '8px' }}>Product Configuration</h3>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          We store the product information you provide, including product name, description, keywords, and
          AI system prompts. This data is used to generate relevant replies to social media posts.
        </p>

        <h3 style={{ fontSize: '16px', fontWeight: 600, marginTop: '16px', marginBottom: '8px' }}>Social Media Credentials (Chrome Extension)</h3>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          When you use our Chrome extension to connect Twitter/X, we access your Twitter session cookies
          (auth_token and ct0) to post replies on your behalf. These credentials are:
        </p>
        <ul style={{ lineHeight: 1.7, color: '#333', paddingLeft: '24px', marginTop: '8px' }}>
          <li>Encrypted using industry-standard encryption (Fernet) before storage</li>
          <li>Only used to post replies that you explicitly approve</li>
          <li>Never shared with third parties</li>
          <li>Can be deleted at any time through the Settings page</li>
        </ul>

        <h3 style={{ fontSize: '16px', fontWeight: 600, marginTop: '16px', marginBottom: '8px' }}>Social Media Content</h3>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          We collect and process publicly available tweets that match your product keywords. We store:
        </p>
        <ul style={{ lineHeight: 1.7, color: '#333', paddingLeft: '24px', marginTop: '8px' }}>
          <li>Tweet content and metadata (author, URL, timestamp)</li>
          <li>AI-generated reply drafts</li>
          <li>Your edits and approval/rejection decisions</li>
          <li>Posted reply references for analytics</li>
        </ul>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>How We Use Your Information</h2>
        <ul style={{ lineHeight: 1.7, color: '#333', paddingLeft: '24px' }}>
          <li>To provide the core service: finding relevant tweets and generating reply suggestions</li>
          <li>To post approved replies to Twitter/X on your behalf</li>
          <li>To display analytics about your engagement activity</li>
          <li>To improve our AI models and reply quality</li>
          <li>To communicate important updates about the service</li>
        </ul>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Chrome Extension Permissions</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          Our Chrome extension requires the following permissions:
        </p>
        <ul style={{ lineHeight: 1.7, color: '#333', paddingLeft: '24px', marginTop: '8px' }}>
          <li><strong>cookies:</strong> To read your Twitter session cookies for authentication</li>
          <li><strong>activeTab:</strong> To interact with Twitter pages when posting replies</li>
          <li><strong>host permission (x.com):</strong> To access Twitter cookies and post replies</li>
        </ul>
        <p style={{ lineHeight: 1.7, color: '#333', marginTop: '12px' }}>
          The extension only accesses these permissions when you actively use it. It does not run in the
          background or collect any data without your explicit action.
        </p>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Data Security</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          We implement appropriate security measures to protect your data:
        </p>
        <ul style={{ lineHeight: 1.7, color: '#333', paddingLeft: '24px', marginTop: '8px' }}>
          <li>Twitter credentials are encrypted at rest using Fernet symmetric encryption</li>
          <li>All data transmission uses HTTPS encryption</li>
          <li>Database access is protected by Row Level Security policies</li>
          <li>API endpoints require authentication</li>
        </ul>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Data Retention</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          We retain your data for as long as your account is active. Queue items (pending and processed
          replies) are retained for analytics purposes. You can request deletion of your account and all
          associated data by contacting us.
        </p>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Third-Party Services</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>We use the following third-party services:</p>
        <ul style={{ lineHeight: 1.7, color: '#333', paddingLeft: '24px', marginTop: '8px' }}>
          <li><strong>Supabase:</strong> Authentication and database hosting</li>
          <li><strong>OpenAI:</strong> AI-powered reply generation (we send tweet content for processing)</li>
          <li><strong>Apify:</strong> Tweet data collection from Twitter/X</li>
          <li><strong>Vercel:</strong> Web application hosting</li>
          <li><strong>Railway:</strong> API server hosting</li>
        </ul>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Your Rights</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>You have the right to:</p>
        <ul style={{ lineHeight: 1.7, color: '#333', paddingLeft: '24px', marginTop: '8px' }}>
          <li>Access your personal data</li>
          <li>Correct inaccurate data</li>
          <li>Delete your account and associated data</li>
          <li>Disconnect your Twitter account at any time</li>
          <li>Export your data</li>
        </ul>
      </section>

      <section style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Contact</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          For privacy-related questions or requests, please contact us through the application dashboard
          or create an issue on our GitHub repository.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '12px' }}>Changes to This Policy</h2>
        <p style={{ lineHeight: 1.7, color: '#333' }}>
          We may update this privacy policy from time to time. We will notify you of significant changes
          through the application or by email.
        </p>
      </section>

      <div style={{ marginTop: '48px', paddingTop: '24px', borderTop: '1px solid #e8e8e8', textAlign: 'center' }}>
        <a href="/" style={{ color: '#111', fontSize: '14px' }}>Back to Operative1</a>
      </div>
    </div>
  )
}
