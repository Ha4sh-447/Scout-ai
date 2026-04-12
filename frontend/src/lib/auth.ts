import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";

export const authOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  session: { strategy: "jwt" as const },
  pages: {
    signIn: "/auth/login",
  },
  callbacks: {
    async jwt({ token, user, account }: any) {
      if (account?.provider === "google" && user) {
        try {
          const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
          const res = await fetch(`${API_URL}/auth/sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: user.email,
              id_token: account.id_token,
              provider: account.provider
            }),
          });
          
          if (res.ok) {
            const data = await res.json();
            token.accessToken = data.access_token;
            token.backendId = data.user_id;
          }
        } catch (error) {
          console.error("Error during social sync in JWT:", error);
        }
      }
      return token;
    },
    async session({ session, token }: any) {
      if (token && session.user) {
        session.user.id = token.backendId || token.sub;
        session.user.accessToken = token.accessToken;
      }
      return session;
    },
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authOptions);
