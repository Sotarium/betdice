import Image from "next/image";

export default function Home() {
  return (
    <main className="home-container">
      <div className="home-content">
        <div className="logo-wrapper">
          <img
            src="/bot-logo.png"
            alt="Dicebet Bot Logo"
            className="bot-logo"
            width={128}
            height={128}
          />
        </div>

        <section className="community" aria-labelledby="community-title">
          <h2 id="community-title" className="community-title">
            Gamble with Dicebet Bot
          </h2>
          <div className="socials">
            {/*[*/}
            <a
              className="social"
              href="https://discord.gg/dejen"
              target="_blank"
              rel="noopener"
            >
              <span className="social-chip" aria-hidden="true">
                <svg className="social-icon">
                  <use href="/brand.svg#discord"></use>
                </svg>
              </span>{" "}
              Discord
            </a>
            {/*]*/}
          </div>
        </section>
      </div>
    </main>
  );
}
