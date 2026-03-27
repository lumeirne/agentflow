import { Auth0Client } from "@auth0/nextjs-auth0/server";

const audience =
	process.env.AUTH0_AUDIENCE ?? process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;

export const auth0 = new Auth0Client({
	authorizationParameters: {
		audience,
		scope: process.env.AUTH0_SCOPE ?? "openid profile email offline_access",
	},
	routes: {
		login: "/api/auth/login",
		logout: "/api/auth/logout",
		callback: "/api/auth/callback",
	},
});
