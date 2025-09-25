FROM nginx:alpine

# Remove default configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom configuration
COPY nginx.conf /etc/nginx/conf.d/

# Create nginx user and group if they don't exist
RUN addgroup -g 1001 nginx && adduser -D -s /bin/false -u 1001 -G nginx nginx || true

# Create log directory
RUN mkdir -p /var/log/nginx

# Set proper permissions
RUN chown -R nginx:nginx /var/log/nginx
RUN chmod -R 755 /var/log/nginx

EXPOSE 80 443