export const createApiKey = async () => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await fetch(`${SCORER_BACKEND}account/api-key`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        AUTHORIZATION: `Bearer ${token}`,
      },
    });
    const data = await response.json();
  } catch (error) {
    console.error(error);
  }
};

export const getApiKeys = async (): Promise<string[]> => {
  try {
    const SCORER_BACKEND = process.env.NEXT_PUBLIC_PASSPORT_SCORER_BACKEND;
    const token = localStorage.getItem("access-token");
    const response = await fetch(`${SCORER_BACKEND}account/api-key`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        AUTHORIZATION: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    return data.map((key: { id: string }) => key.id);
  } catch (error) {
    throw error;
  }
};
