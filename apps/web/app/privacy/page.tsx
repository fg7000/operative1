export const metadata = {
  title: 'Privacy Policy - Operative1',
  description: 'Privacy policy for Operative1 Chrome extension and web application',
}

export default function PrivacyPage() {
  return (
    <div style={{
      maxWidth: '800px',
      margin: '0 auto',
      padding: '60px 24px 100px',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#1a1a1a',
      lineHeight: 1.7,
      backgroundColor: '#fff',
    }}>
      <h1 style={{
        fontSize: '36px',
        fontWeight: 700,
        marginBottom: '32px',
        letterSpacing: '-0.02em',
        color: '#000',
      }}>
        Operative1 Privacy Policy
      </h1>

      <div style={{
        padding: '24px',
        background: '#f9fafb',
        borderRadius: '8px',
        marginBottom: '48px',
        borderLeft: '4px solid #000',
      }}>
        <p style={{ margin: '0 0 8px 0', fontSize: '15px', color: '#555' }}>
          <strong>Effective date:</strong> March 13, 2026
        </p>
        <p style={{ margin: '0 0 16px 0', fontSize: '15px', color: '#555' }}>
          <strong>Last updated:</strong> March 13, 2026
        </p>
        <p style={{ margin: 0, fontSize: '16px', color: '#333' }}>
          This privacy policy describes how Operative1 (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;) collects, uses, and protects your information when you use our Chrome extension and web dashboard.
        </p>
      </div>

      <Section num={1} title="What We Collect">
        <p>When you use the Operative1 Chrome extension, we collect:</p>
        <ul>
          <li><strong>Twitter/X authentication cookies</strong> (auth_token and ct0) when you click &quot;Connect Twitter&quot; in the extension</li>
          <li><strong>Your Operative1 account email</strong> for linking your Twitter connection to your account</li>
        </ul>
        <p style={{ marginTop: '16px' }}><strong>We do NOT collect:</strong></p>
        <ul>
          <li>Browsing history</li>
          <li>Personal messages or DMs</li>
          <li>Location data</li>
          <li>Financial information</li>
          <li>Health data</li>
        </ul>
      </Section>

      <Section num={2} title="How We Use Your Data">
        <ul>
          <li>Authentication cookies are used <strong>solely</strong> to post replies and content you have approved through the Operative1 dashboard</li>
          <li>Cookies are stored encrypted on our servers and linked to your Operative1 account</li>
          <li>We <strong>never</strong> use your cookies to read your DMs, access your personal data, or perform any action you haven&apos;t approved</li>
        </ul>
      </Section>

      <Section num={3} title="Data Storage and Security">
        <ul>
          <li>All credentials are encrypted using industry-standard <strong>AES encryption</strong> before storage</li>
          <li>Credentials are only decrypted at the moment of posting an approved reply</li>
          <li>Our servers are hosted on Railway with encrypted connections (HTTPS/TLS)</li>
        </ul>
      </Section>

      <Section num={4} title="Third-Party Sharing">
        <ul>
          <li>We <strong>never sell, share, or transfer</strong> your credentials to any third party</li>
          <li>We <strong>never share</strong> your Twitter session with advertisers, analytics providers, or any external service</li>
          <li>The <strong>only</strong> external service that receives your credentials is Twitter/X itself, when posting content you approved</li>
        </ul>
      </Section>

      <Section num={5} title="Your Controls">
        <ul>
          <li><strong>Disconnect anytime:</strong> Remove your Twitter account from the Operative1 Settings page</li>
          <li><strong>Permanent deletion:</strong> Disconnecting permanently deletes your stored credentials from our servers</li>
          <li><strong>Instant stop:</strong> Uninstalling the Chrome extension immediately stops all posting activity</li>
          <li><strong>Full transparency:</strong> Review all pending and posted content in your Operative1 dashboard</li>
        </ul>
      </Section>

      <Section num={6} title="Chrome Extension Permissions">
        <ul>
          <li><strong>&quot;cookies&quot; permission:</strong> Used to read your Twitter/X authentication cookies when you click Connect. Only reads cookies from the x.com domain.</li>
          <li><strong>&quot;activeTab&quot; permission:</strong> Used to detect if you are logged into Twitter/X</li>
        </ul>
        <p style={{ marginTop: '16px' }}>The extension does <strong>not</strong>:</p>
        <ul>
          <li>Access any other websites</li>
          <li>Track your browsing history</li>
          <li>Modify any web pages</li>
        </ul>
      </Section>

      <Section num={7} title="Data Retention">
        <ul>
          <li>Your credentials are stored as long as your Twitter account is connected</li>
          <li>Upon disconnection, credentials are <strong>permanently deleted within 24 hours</strong></li>
          <li>Account deletion removes all associated data including credentials, posting history, and analytics</li>
        </ul>
      </Section>

      <Section num={8} title="Contact">
        <p>For privacy questions or concerns:</p>
        <p style={{ margin: '12px 0' }}>
          <strong>Email:</strong>{' '}
          <a href="mailto:faryar.ghazanfari@gmail.com" style={{ color: '#000', textDecoration: 'underline' }}>
            faryar.ghazanfari@gmail.com
          </a>
        </p>
        <p>For data deletion requests, email us and we will process your request within 48 hours.</p>
      </Section>

      <Section num={9} title="Legal Basis for Processing (GDPR)">
        <ul>
          <li>We process your data based on your <strong>explicit consent</strong> when you click &quot;Connect Twitter&quot;</li>
          <li>You may withdraw consent at any time by disconnecting your account in Settings</li>
          <li>Upon withdrawal, all stored data is permanently deleted</li>
        </ul>
      </Section>

      <Section num={10} title="International Data Transfers">
        <ul>
          <li>Our servers are located in the <strong>United States</strong> (Railway hosting, AWS infrastructure)</li>
          <li>Data is transferred securely using TLS/HTTPS encryption</li>
          <li>By using Operative1, you consent to the transfer of your data to the United States</li>
        </ul>
      </Section>

      <Section num={11} title="Children's Privacy">
        <ul>
          <li>Operative1 is <strong>not intended for use by anyone under the age of 16</strong></li>
          <li>We do not knowingly collect data from children</li>
          <li>If we learn we have collected data from a child under 16, we will delete it immediately</li>
        </ul>
      </Section>

      <Section num={12} title="California Privacy Rights (CCPA)">
        <ul>
          <li>California residents have the right to know what data we collect</li>
          <li>You have the right to request deletion of your data</li>
          <li>You have the right to opt out of the sale of your data — <strong>we never sell your data</strong></li>
          <li>To exercise these rights, contact us at the email above</li>
        </ul>
      </Section>

      <Section num={13} title="Changes to This Policy">
        <ul>
          <li>We may update this privacy policy from time to time</li>
          <li>Changes will be posted on this page with an updated &quot;Last updated&quot; date</li>
          <li>Continued use of Operative1 after changes constitutes acceptance of the updated policy</li>
        </ul>
      </Section>

      <Section num={14} title="Data Breach Notification">
        <ul>
          <li>In the event of a data breach affecting your credentials, we will notify affected users <strong>within 72 hours</strong> via email</li>
          <li>We will immediately rotate or invalidate any compromised credentials</li>
          <li>We will notify relevant authorities as required by applicable law</li>
        </ul>
      </Section>

      <Section num={15} title="Cookies Used by the Extension">
        <ul>
          <li><strong>auth_token:</strong> Twitter/X session authentication token. Used to authenticate posting requests.</li>
          <li><strong>ct0:</strong> Twitter/X CSRF protection token. Required for secure API requests.</li>
        </ul>
        <p style={{ marginTop: '16px' }}><strong>Important:</strong></p>
        <ul>
          <li>These cookies are <strong>READ from your browser</strong>, not created by our extension</li>
          <li>No tracking cookies, analytics cookies, or advertising cookies are used by our extension</li>
        </ul>
      </Section>

      <Section num={16} title="Open Source">
        <ul>
          <li>
            The Operative1 Chrome extension source code is available at{' '}
            <a
              href="https://github.com/fg7000/operative1"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#000', textDecoration: 'underline' }}
            >
              github.com/fg7000/operative1
            </a>
          </li>
          <li>Users can inspect exactly what the extension does before installing</li>
        </ul>
      </Section>

      <div style={{
        marginTop: '64px',
        paddingTop: '24px',
        borderTop: '1px solid #e5e5e5',
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
          &larr; Back to Operative1
        </a>
      </div>
    </div>
  )
}

function Section({ num, title, children }: { num: number; title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: '40px' }}>
      <h2 style={{
        fontSize: '20px',
        fontWeight: 600,
        marginBottom: '16px',
        color: '#000',
      }}>
        {num}. {title}
      </h2>
      <div style={{ color: '#333', fontSize: '16px' }}>
        {children}
        <style>{`
          section ul {
            margin: 8px 0;
            padding-left: 24px;
          }
          section li {
            margin-bottom: 10px;
          }
          section p {
            margin: 0 0 12px 0;
          }
        `}</style>
      </div>
    </section>
  )
}
