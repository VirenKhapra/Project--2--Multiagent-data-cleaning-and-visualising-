import React from "react";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("App render error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="ff-page-grid" style={{ minHeight: "100vh", padding: "32px" }}>
          <section className="ff-panel" style={{ border: "2px solid #ef4444" }}>
            <p className="ff-eyebrow" style={{ color: "#ef4444" }}>Something went wrong</p>
            <h2>We hit an unexpected UI error.</h2>
            <p className="ff-copy-muted">
              Refresh the page to try again. If the problem continues, check the latest frontend changes or backend response shape.
            </p>
            {this.state.error && (
              <div style={{
                marginTop: "24px",
                padding: "16px",
                backgroundColor: "#fef2f2",
                color: "#991b1b",
                border: "1px solid #fee2e2",
                borderRadius: "6px",
                overflow: "auto",
                fontFamily: "monospace",
                textAlign: "left"
              }}>
                <strong style={{ fontSize: "16px" }}>{this.state.error.toString()}</strong>
                <pre style={{
                  marginTop: "12px",
                  fontSize: "12px",
                  whiteSpace: "pre-wrap",
                  lineHeight: "1.5",
                  backgroundColor: "#fff",
                  padding: "12px",
                  border: "1px solid #fee2e2",
                  borderRadius: "4px"
                }}>
                  {this.state.error.stack}
                </pre>
              </div>
            )}
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
