import createNextIntlPlugin from "next-intl/plugin";

// Points at ./i18n/request.ts by default.
const withNextIntl = createNextIntlPlugin();

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

export default withNextIntl(nextConfig);
