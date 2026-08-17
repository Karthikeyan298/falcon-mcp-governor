import { HttpInterceptorFn } from '@angular/common/http';

/** Sends the session cookie on every API request -- login relies on it. */
export const credentialsInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req.clone({ withCredentials: true }));
};
