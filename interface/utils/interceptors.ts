import axios, { AxiosError } from "axios";

export const unAuthorizedInterceptor = (logout: () => void) => {
  const interceptor = axios.interceptors.response.use(
    (response) => {
      return response;
    },
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          logout();
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.response.eject(interceptor);
    };
};

export const headerInterceptor = () => {
  const requestInterceptor = axios.interceptors.request.use((config) => {
    const token = localStorage.getItem("access-token");
    if (config && config.headers && token) {
      config.headers["Content-Type"] = "application/json";
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  });

  return () => {
    axios.interceptors.response.eject(requestInterceptor);
  };
};
