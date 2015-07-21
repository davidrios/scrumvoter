begin;
create table sprints (
	id serial primary key,
	name varchar(255),
	sprint_date timestamp with time zone
);

create table tasks (
	id serial primary key,
	sprint_id integer references sprints,
	description text,
	ordering integer
);

create table users (
	id serial primary key,
	name varchar(255)
);

create table task_votes (
	task_id integer not null references tasks,
	user_id integer not null references users,
	value integer not null,
	primary key (task_id, user_id)
);
commit;