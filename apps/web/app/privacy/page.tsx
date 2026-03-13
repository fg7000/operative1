export const metadata = {
  title: 'Privacy Policy - Operative1',
  description: 'Privacy policy for Operative1 Chrome extension and web application',
}

export default function PrivacyPage() {
  return (
    <div style={{
      maxWidth: '760px',
      margin: '0 auto',
      padding: '60px 24px 80px',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#111',
      lineHeight: 1.75,
    }}>
      <h1 style={{ fontSize: '32px', fontWeight: 700, marginBottom: '24px', letterSpacing: '-0.02em' }}>
        Operative1 Privacy Policy
      </h1>

      <div style={{
        padding: '20px 24px',
        background: '#f8f9fa',
        borderRadius: '8px',
        marginBottom: '40px',
        fontSize: '14px',
        color: '#444',
      }}>
        <div style={{ marginBottom: '8px' }}>
          <strong>Effective date:</strong> March 13, 2026
        </div>
        <div style={{ marginBottom: '16px' }}>
          <strong>Last updated:</strong> March 13, 2026
        </div>
        <p style={{ margin: 0, lineHeight: 1.7 }}>
          This privacy policy describes how Operative1 ("we", "us", "our") collects, uses, and protects
          your information when you use our Chrome extension and web dashboard.
        </p>
      </div>

      <Section number={1} title="What We Collect">
        <p>When you use the Operative1 Chrome extension and web application, we collect:</p>
        <ul>
          <li>
            <strong>Twitter/X authentication cookies</strong> (auth_token and ct0) — collected only when
            you explicitly click "Connect Twitter" in the extension
          </li>
          <li>
            <strong>Your Operative1 account email</strong> — used for account management and linking
            your Twitter connection
          </li>
          <li>
            <strong>Product configuration data</strong> — keywords, system prompts, and settings you
            configure for your products
          </li>
          <li>
            <strong>Reply queue data</strong> — tweets you interact with and replies generated for your review
          </li>
        </ul>
        <p style={{ marginTop: '20px' }}><strong>We do NOT collect:</strong></p>
        <ul>
          <li>Browsing history or web activity</li>
          <li>Personal messages, DMs, or private communications</li>
          <li>Location or geolocation data</li>
          <li>Financial or payment information</li>
          <li>Health or biometric data</li>
          <li>Data from any website other than x.com and twitter.com</li>
          <li>Your Twitter password (we only access session cookies)</li>
        </ul>
      </Section>

      <Section number={2} title="How We Use Your Data">
        <ul>
          <li>
            <strong>Authentication cookies</strong> are used solely to post replies and content you have
            explicitly approved through the Operative1 dashboard
          </li>
          <li>
            <strong>Account email</strong> is used for authentication, account management, and important
            service communications
          </li>
          <li>
            <strong>Product data</strong> is used to find relevant conversations and generate appropriate
            reply suggestions
          </li>
          <li>
            We <strong>never</strong> use your cookies to read your DMs, access private data, follow/unfollow
            accounts, like posts, or perform any action you haven't explicitly approved
          </li>
          <li>
            Every post made through Operative1 requires your explicit approval, or approval by Autopilot
            rules that you configure
          </li>
        </ul>
      </Section>

      <Section number={3} title="Data Storage and Security">
        <ul>
          <li>
            All credentials are encrypted using industry-standard <strong>AES-256 encryption</strong> before storage
          </li>
          <li>
            Encryption keys are stored separately from encrypted data
          </li>
          <li>
            Credentials are only decrypted at the moment of posting an approved reply, then immediately
            cleared from memory
          </li>
          <li>
            All data transmission uses <strong>HTTPS/TLS encryption</strong>
          </li>
          <li>
            Our servers are hosted on Railway with encrypted connections and regular security updates
          </li>
          <li>
            Database access is protected by Row Level Security (RLS) policies
          </li>
          <li>
            All API endpoints require authentication
          </li>
        </ul>
      </Section>

      <Section number={4} title="Third-Party Sharing">
        <ul>
          <li>
            We <strong>never sell, rent, or trade</strong> your personal information or credentials to any third party
          </li>
          <li>
            We <strong>never share</strong> your Twitter session with advertisers, analytics providers,
            data brokers, or any external service
          </li>
          <li>
            The <strong>only</strong> external service that receives your credentials is Twitter/X itself,
            when posting content you have approved
          </li>
          <li>
            We use the following service providers who may process data on our behalf:
            <ul style={{ marginTop: '8px' }}>
              <li><strong>Supabase</strong> — Authentication and database hosting</li>
              <li><strong>Railway</strong> — API server hosting</li>
              <li><strong>Vercel</strong> — Web application hosting</li>
              <li><strong>OpenRouter/OpenAI</strong> — AI processing for reply generation (tweet content only, no credentials)</li>
            </ul>
          </li>
        </ul>
      </Section>

      <Section number={5} title="Your Controls">
        <ul>
          <li>
            <strong>Disconnect anytime:</strong> Remove your Twitter connection instantly from the
            Operative1 Settings page
          </li>
          <li>
            <strong>Permanent deletion:</strong> Disconnecting permanently and irreversibly deletes
            your stored credentials from our servers
          </li>
          <li>
            <strong>Instant stop:</strong> Uninstalling the Chrome extension immediately stops all
            posting activity
          </li>
          <li>
            <strong>Full transparency:</strong> Review all pending, posted, and rejected content in
            your Operative1 dashboard
          </li>
          <li>
            <strong>Edit before posting:</strong> Modify any AI-generated reply before approval
          </li>
          <li>
            <strong>Data export:</strong> Request a copy of your data by contacting us
          </li>
          <li>
            <strong>Account deletion:</strong> Request complete deletion of your account and all
            associated data
          </li>
        </ul>
      </Section>

      <Section number={6} title="Chrome Extension Permissions">
        <p>Our Chrome extension requests the following permissions:</p>
        <ul>
          <li>
            <strong>"cookies" permission:</strong> Used to read your Twitter/X authentication cookies
            when you click Connect. Only reads cookies from the x.com domain. Does not access cookies
            from any other website.
          </li>
          <li>
            <strong>"host_permissions" for x.com and twitter.com:</strong> Required to access Twitter
            cookies and make authenticated requests to Twitter's API for posting.
          </li>
        </ul>
        <p style={{ marginTop: '20px' }}>The extension does <strong>NOT</strong>:</p>
        <ul>
          <li>Access any websites other than x.com and twitter.com</li>
          <li>Track your browsing history or web activity</li>
          <li>Inject content into or modify any web pages</li>
          <li>Run continuously in the background</li>
          <li>Collect any data without your explicit action (clicking "Connect")</li>
          <li>Access your Twitter password</li>
          <li>Store any data locally on your device beyond the current session</li>
        </ul>
      </Section>

      <Section number={7} title="Data Retention">
        <ul>
          <li>
            <strong>Credentials:</strong> Stored only while your Twitter account is connected.
            Permanently deleted within 24 hours of disconnection.
          </li>
          <li>
            <strong>Reply queue data:</strong> Retained for 90 days for analytics and audit purposes,
            then automatically deleted.
          </li>
          <li>
            <strong>Account data:</strong> Retained until you delete your account. Upon account deletion,
            all data is permanently removed within 30 days.
          </li>
          <li>
            <strong>Backups:</strong> Encrypted backups may persist for up to 30 days after deletion
            for disaster recovery purposes, after which they are purged.
          </li>
        </ul>
      </Section>

      <Section number={8} title="Contact">
        <p>For privacy questions, concerns, or requests:</p>
        <p style={{ margin: '12px 0' }}>
          <strong>Email:</strong>{' '}
          <a href="mailto:faryar.ghazanfari@gmail.com" style={{ color: '#111' }}>
            faryar.ghazanfari@gmail.com
          </a>
        </p>
        <p>
          For data deletion requests, email us and we will process your request within 48 hours.
          Please include "Data Deletion Request" in your subject line.
        </p>
      </Section>

      <Section number={9} title="Legal Basis for Processing (GDPR)">
        <p>For users in the European Economic Area (EEA), we process your data based on:</p>
        <ul>
          <li>
            <strong>Explicit consent:</strong> When you click "Connect Twitter" in the extension, you
            provide explicit consent for us to access and store your authentication cookies
          </li>
          <li>
            <strong>Contract performance:</strong> Processing necessary to provide the Operative1 service
            you have signed up for
          </li>
          <li>
            <strong>Legitimate interests:</strong> Processing necessary for security, fraud prevention,
            and service improvement
          </li>
        </ul>
        <p style={{ marginTop: '16px' }}>
          You may <strong>withdraw consent at any time</strong> by disconnecting your Twitter account
          in Settings. Upon withdrawal, all stored credentials are permanently deleted.
        </p>
      </Section>

      <Section number={10} title="International Data Transfers">
        <ul>
          <li>
            Our servers are located in the <strong>United States</strong> (Railway hosting on AWS infrastructure)
          </li>
          <li>
            All data transfers are protected using TLS/HTTPS encryption
          </li>
          <li>
            By using Operative1, you consent to the transfer and processing of your data in the United States
          </li>
          <li>
            For EEA users: We rely on Standard Contractual Clauses (SCCs) as approved by the European
            Commission for data transfers outside the EEA
          </li>
        </ul>
      </Section>

      <Section number={11} title="Children's Privacy">
        <ul>
          <li>
            Operative1 is <strong>not intended for use by anyone under the age of 16</strong>
          </li>
          <li>
            We do not knowingly collect personal information from children under 16
          </li>
          <li>
            If we learn that we have inadvertently collected data from a child under 16, we will
            delete that information immediately
          </li>
          <li>
            If you believe a child has provided us with personal information, please contact us
            immediately at the email address above
          </li>
        </ul>
      </Section>

      <Section number={12} title="California Privacy Rights (CCPA)">
        <p>If you are a California resident, you have the following rights under the California Consumer Privacy Act:</p>
        <ul>
          <li>
            <strong>Right to know:</strong> You may request disclosure of the personal information we
            have collected about you
          </li>
          <li>
            <strong>Right to delete:</strong> You may request deletion of your personal information
          </li>
          <li>
            <strong>Right to opt-out:</strong> You have the right to opt out of the "sale" of your
            personal information — <strong>we never sell your data</strong>
          </li>
          <li>
            <strong>Right to non-discrimination:</strong> We will not discriminate against you for
            exercising your privacy rights
          </li>
        </ul>
        <p style={{ marginTop: '16px' }}>
          To exercise these rights, contact us at{' '}
          <a href="mailto:faryar.ghazanfari@gmail.com" style={{ color: '#111' }}>
            faryar.ghazanfari@gmail.com
          </a>
          . We will respond within 45 days as required by law.
        </p>
      </Section>

      <Section number={13} title="Changes to This Policy">
        <ul>
          <li>
            We may update this privacy policy from time to time to reflect changes in our practices
            or applicable laws
          </li>
          <li>
            Changes will be posted on this page with an updated "Last updated" date at the top
          </li>
          <li>
            For material changes, we will notify users via email or a prominent notice in the dashboard
          </li>
          <li>
            Continued use of Operative1 after changes are posted constitutes acceptance of the updated policy
          </li>
          <li>
            We encourage you to review this policy periodically
          </li>
        </ul>
      </Section>

      <Section number={14} title="Data Breach Notification">
        <p>In the unlikely event of a data breach affecting your credentials or personal information:</p>
        <ul>
          <li>
            We will <strong>notify affected users within 72 hours</strong> via the email address
            associated with their account
          </li>
          <li>
            We will immediately rotate, invalidate, or delete any compromised credentials
          </li>
          <li>
            We will notify relevant supervisory authorities as required by applicable law (including
            GDPR requirements for EEA users)
          </li>
          <li>
            We will provide clear information about what data was affected and recommended actions
          </li>
          <li>
            We maintain incident response procedures and conduct regular security assessments
          </li>
        </ul>
      </Section>

      <Section number={15} title="Cookies Used by the Extension">
        <p>
          The Operative1 extension reads (but does not create) the following cookies from your browser
          when you click "Connect Twitter":
        </p>
        <ul>
          <li>
            <strong>auth_token:</strong> Twitter/X session authentication token. Used to authenticate
            posting requests to Twitter's API. This cookie is set by Twitter when you log in.
          </li>
          <li>
            <strong>ct0:</strong> Twitter/X CSRF (Cross-Site Request Forgery) protection token.
            Required by Twitter for secure API requests. This cookie is set by Twitter.
          </li>
        </ul>
        <p style={{ marginTop: '16px' }}><strong>Important:</strong></p>
        <ul>
          <li>These cookies are <strong>read from your browser</strong>, not created by our extension</li>
          <li>We do not use any tracking cookies, analytics cookies, or advertising cookies</li>
          <li>Our extension does not set any cookies on any website</li>
          <li>The cookies are only accessed when you explicitly click "Connect Twitter"</li>
        </ul>
      </Section>

      <Section number={16} title="Open Source">
        <ul>
          <li>
            The Operative1 Chrome extension source code is publicly available at{' '}
            <a
              href="https://github.com/fg7000/operative1"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#111' }}
            >
              github.com/fg7000/operative1
            </a>
          </li>
          <li>
            Users can inspect exactly what the extension does before installing
          </li>
          <li>
            We welcome security researchers to review our code and report any vulnerabilities
          </li>
          <li>
            The extension code in the Chrome Web Store matches the public repository
          </li>
        </ul>
      </Section>

      <div style={{
        marginTop: '60px',
        paddingTop: '24px',
        borderTop: '1px solid #e0e0e0',
        fontSize: '14px',
        color: '#666',
        textAlign: 'center',
      }}>
        <p style={{ marginBottom: '16px' }}>
          If you have any questions about this Privacy Policy, please contact us at{' '}
          <a href="mailto:faryar.ghazanfari@gmail.com" style={{ color: '#444' }}>
            faryar.ghazanfari@gmail.com
          </a>
        </p>
        <a
          href="/"
          style={{
            color: '#111',
            fontSize: '14px',
            textDecoration: 'none',
            fontWeight: 500,
          }}
        >
          Back to Operative1
        </a>
      </div>
    </div>
  )
}

function Section({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: '36px' }}>
      <h2 style={{
        fontSize: '18px',
        fontWeight: 600,
        marginBottom: '14px',
        color: '#111',
      }}>
        {number}. {title}
      </h2>
      <div style={{
        color: '#333',
        fontSize: '15px',
      }}>
        {children}
        <style>{`
          section ul {
            margin: 8px 0;
            padding-left: 24px;
          }
          section li {
            margin-bottom: 10px;
          }
          section li ul {
            margin-top: 8px;
          }
          section li ul li {
            margin-bottom: 6px;
          }
          section p {
            margin: 0 0 12px 0;
          }
        `}</style>
      </div>
    </section>
  )
}
