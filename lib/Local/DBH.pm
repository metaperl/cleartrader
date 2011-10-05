package Local::DBH;

use strict;
use warnings;

use base qw(DBIx::DBH);


my $config = DBIx::DBH->new
  (
    #debug => 1,

   username => $main::sharedusername,
   password => $main::sharedpassword,


   dsn  => { driver => 'Pg',    dbname => 'biotrackthc', 
	     port => $main::sharedport,    sslmode => $main::sharedssl,    host => $main::sharedhost, },
   attr => { RaiseError => 1 }
  );

sub new {
  my($self)=@_;
  DBIx::DBH->new(%$config);
}

1;
