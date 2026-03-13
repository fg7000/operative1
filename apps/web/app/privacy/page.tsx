export const metadata = {
  title: 'Privacy Policy - Operative1',
  description: 'Privacy policy for Operative1 Chrome extension and web application',
}

export default function PrivacyPage() {
  return (
    <div style={{
      maxWidth: '720px',
      margin: '0 auto',
      padding: '60px 24px',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#111',
      lineHeight: 1.7,
    }}>
      <h1 style={{ fontSize: '36px', fontWeight: 600, marginBottom: '8px', letterSpacing: '-0.02em' }}>
        Operative1 Privacy Policy
      </h1>
      <p style={{ color: '#666', marginBottom: '48px', fontSize: '14px' }}>
        Last updated: March 13, 2026
      </p>

      <Section title="1. What We Collect">
        <p>When you use the Operative1 Chrome extension and web application, we collect:</p>
        <ul>
          <li>
            <strong>Twitter/X authentication cookies</strong> (auth_token and ct0) when you click
            "Connect Twitter" in the extension
          </li>
          <li>
            <strong>Your Operative1 account email</strong> for linking your Twitter connection to your account
          </li>
        </ul>
        <p style={{ marginTop: '16px' }}>
          <strong>We do NOT collect:</strong>
        </p>
        <ul>
          <li>Browsing history</li>
          <li>Personal messages or DMs</li>
          <li>Location data</li>
          <li>Financial information</li>
          <li>Health data</li>
          <li>Any data from websites other than x.com/twitter.com</li>
        </ul>
      </Section>

      <Section title="2. How We Use Your Data">
        <ul>
          <li>
            Authentication cookies are used <strong>solely</strong> to post replies and content you have
            explicitly approved through the Operative1 dashboard
          </li>
          <li>
            Cookies are stored encrypted on our servers and linked to your Operative1 account
          </li>
          <li>
            We <strong>never</strong> use your cookies to read your DMs, access your personal data,
            or perform any action you haven't approved
          </li>
          <li>
            Every post made through Operative1 requires your explicit approval (or Autopilot approval
            based on rules you configure)
          </li>
        </ul>
      </Section>

      <Section title="3. Data Storage and Security">
        <ul>
          <li>
            All credentials are encrypted using industry-standard <strong>AES encryption</strong> before storage
          </li>
          <li>
            Credentials are only decrypted at the moment of posting an approved reply
          </li>
          <li>
            Our servers are hosted on Railway with encrypted connections (HTTPS/TLS)
          </li>
          <li>
            Database access is protected by Row Level Security policies
          </li>
          <li>
            API endpoints require authentication
          </li>
        </ul>
      </Section>

      <Section title="4. Third-Party Sharing">
        <ul>
          <li>
            We <strong>never sell, share, or transfer</strong> your credentials to any third party
          </li>
          <li>
            We <strong>never share</strong> your Twitter session with advertisers, analytics providers,
            or any external service
          </li>
          <li>
            The <strong>only</strong> external service that receives your credentials is Twitter/X itself,
            when posting content you approved
          </li>
        </ul>
      </Section>

      <Section title="5. Your Controls">
        <ul>
          <li>
            <strong>Disconnect anytime:</strong> Remove your Twitter connection from the Operative1 Settings page
          </li>
          <li>
            <strong>Permanent deletion:</strong> Disconnecting permanently deletes your stored credentials
            from our servers
          </li>
          <li>
            <strong>Instant stop:</strong> Uninstalling the Chrome extension immediately stops all posting activity
          </li>
          <li>
            <strong>Full transparency:</strong> Review all pending and posted content in your Operative1 dashboard
          </li>
          <li>
            <strong>Edit before posting:</strong> Modify any AI-generated reply before approval
          </li>
        </ul>
      </Section>

      <Section title="6. Chrome Extension Permissions">
        <ul>
          <li>
            <strong>"cookies" permission:</strong> Used to read your Twitter/X authentication cookies when
            you click Connect. Only reads cookies from the x.com domain. Does not access cookies from any
            other website.
          </li>
          <li>
            <strong>"host_permissions" for x.com:</strong> Required to access Twitter cookies and post
            replies to Twitter's API.
          </li>
        </ul>
        <p style={{ marginTop: '16px' }}>
          The extension does <strong>not</strong>:
        </p>
        <ul>
          <li>Access any other websites</li>
          <li>Track your browsing history</li>
          <li>Modify any web pages</li>
          <li>Run in the background when not actively posting</li>
          <li>Collect any data without your explicit action</li>
        </ul>
      </Section>

      <Section title="7. Data Retention">
        <ul>
          <li>
            Your credentials are stored only as long as your Twitter account is connected
          </li>
          <li>
            Upon disconnection, credentials are <strong>permanently deleted within 24 hours</strong>
          </li>
          <li>
            Account deletion removes all associated data including credentials, posting history,
            and analytics
          </li>
          <li>
            Posted reply records are retained for your analytics and audit purposes
          </li>
        </ul>
      </Section>

      <Section title="8. Contact">
        <p>
          For privacy questions or concerns:<br />
          <a href="mailto:faryar.ghazanfari@gmail.com" style={{ color: '#111', fontWeight: 500 }}>
            faryar.ghazanfari@gmail.com
          </a>
        </p>
        <p style={{ marginTop: '12px' }}>
          For data deletion requests, email us and we will process your request within 48 hours.
        </p>
      </Section>

      <div style={{
        marginTop: '64px',
        paddingTop: '32px',
        borderTop: '1px solid #e8e8e8',
        textAlign: 'center',
      }}>
        <a
          href="/"
          style={{
            color: '#666',
            fontSize: '14px',
            textDecoration: 'none',
          }}
        >
          Back to Operative1
        </a>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: '40px' }}>
      <h2 style={{
        fontSize: '20px',
        fontWeight: 600,
        marginBottom: '16px',
        color: '#111',
      }}>
        {title}
      </h2>
      <div style={{
        color: '#333',
        fontSize: '15px',
      }}>
        {children}
        <style>{`
          section ul {
            margin: 0;
            padding-left: 24px;
          }
          section li {
            margin-bottom: 8px;
          }
          section p {
            margin: 0 0 12px 0;
          }
        `}</style>
      </div>
    </section>
  )
}
