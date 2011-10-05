package Local::PayPal::Config;

use Moose;

has 'username' => ( is => 'ro', default => 'thequietcenter_api1.gmail.com' );
has 'password' => ( is => 'ro', default => 'KSZ2KMCVEWCACN49' );
has 'signature' => (
    is      => 'ro',
    default => 'ADI1IIF-7gH5jPewBwlIkmbD6heWA8q34m5i5FEDMsBuP32UhD0dxRGk'
);

1;
